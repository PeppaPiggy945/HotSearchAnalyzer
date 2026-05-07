# analytics/llm_classifier.py
"""
基于轻量语言模型的事件分类器
使用本地 Qwen2.5-3B-Instruct 进行零样本分类，替代关键词匹配方案。

依赖: transformers, torch, modelscope（ModelScope 下载源）
安装: pip install transformers torch modelscope

模型路径在 config/user_config.yaml 的 [llm] 节中配置。
支持 ModelScope 模型ID 或本地路径，例如:
  - "qwen/Qwen2.5-3B-Instruct"          (ModelScope 自动下载)
  - "D:/models/Qwen2.5-3B-Instruct"      (本地路径)
"""


import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from core.models import EventType, EVENT_TYPE_CONFIG
from core.logger import get_logger
from analytics.llm_cache import LLMCache

logger = get_logger(__name__)

# ============================================================
# 检测依赖是否可用（不可用时静默降级，不影响原有功能）
# ============================================================
try:
    import torch
    LLM_TORCH_AVAILABLE = True
except ImportError:
    LLM_TORCH_AVAILABLE = False

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    LLM_TRANSFORMERS_AVAILABLE = True
except ImportError:
    LLM_TRANSFORMERS_AVAILABLE = False

LLM_AVAILABLE = LLM_TORCH_AVAILABLE and LLM_TRANSFORMERS_AVAILABLE


# ============================================================
# Prompt 模板
# ============================================================
SYSTEM_PROMPT = """你是一个新闻热搜事件分类器。根据给定的标题，为该事件选择一个最合适的分类名称。

规则：
- 只返回一个类别名称（2~6个字的中文），不要返回任何其他内容
- 类别应尽量聚合，不要过于细分。例如"科技数码"、"AI人工智能"应合并为"科技"
- 只能从以下类别中选择一个：科技、经济、娱乐、体育、社会、国际、政治、其他
- 如果标题涉及"苹果、华为、小米等公司的产品发布/技术突破、航空航天、人工智能"等话题 → 科技
- 如果标题涉及"股市、基金、房价、通胀、财经"等金融话题 → 经济
- 如果标题涉及"电影、综艺、明星、演唱会、八卦、搞笑趣闻、网红、恋爱"等话题 → 娱乐
- 如果标题涉及"比赛、赛事、球员、比分、球队"等话题 → 体育
- 如果标题涉及"外交、联合国、美国、日本"等国际事务 → 国际
- 如果标题涉及"民生、教育、医疗、事故"等国内事务 → 社会
- 如果标题涉及"政策、政府、会议"等政务话题 → 政治
- 实在无法归类时返回"其他\"

注意：判断时以主标题为核心依据，不要被次要标题带偏分类方向。"""

BATCH_CLASSIFY_PROMPT = """以下有 {count} 组标题，每组用"---"分隔。请对每组判断事件类型。
只返回 {count} 个类别名称（2~6个字的中文），每行一个，顺序与输入对应。
类别应尽量聚合不要过于细分。常见参考：科技、经济、娱乐、体育、社会、国际、政治、军事、教育、健康、文化、财经、房产、汽车、环保、其他

{items}"""


# ============================================================
# 中文类别名 → EventType 枚举
# ============================================================
_CN_TO_EVENT_TYPE = {cn: getattr(EventType, key.upper()) for key, cn, _, _ in EVENT_TYPE_CONFIG}
_CN_TO_EVENT_TYPE["其他"] = EventType.OTHER

# 别名归一化：将模型可能输出的同义类别名统一到标准类别
_CATEGORY_ALIASES = {
    "财经": "经济", "金融": "经济", "理财": "经济", "商业": "经济",
    "搞笑": "娱乐", "八卦": "娱乐", "综艺": "娱乐", "网红": "娱乐",
    "军事": "政治", "国防": "政治",
    "教育": "社会", "健康": "社会", "医疗": "社会", "民生": "社会",
    "房产": "经济", "汽车": "经济",
    "文化": "其他", "环保": "社会",
}



class LLMEventClassifier:
    """
    基于轻量 LLM 的事件分类器

    支持两种模式:
    - local: 本地部署模型（Qwen2.5-3B-Instruct 等），首次运行自动下载
    - api:   远程 API 调用（DeepSeek / 通义千问等），需要配置 API Key

    用法:
        classifier = LLMEventClassifier()              # 默认 local 模式
        classifier = LLMEventClassifier(mode="api")    # API 模式
        classifier = LLMEventClassifier(enabled=False) # 禁用（降级到关键词）

        # 单条分类
        event_type = classifier.classify("苹果发布新iPhone")

        # 批量分类（推荐，效率更高）
        results = classifier.classify_batch([
            "苹果发布新iPhone",
            "A股三大指数集体上涨",
            "某明星官宣结婚",
        ])
    """

    def __init__(
        self,
        mode: str = None,
        model_name: str = None,
        enabled: bool = None,
        batch_size: int = None,
        max_retries: int = 3,
        api_base_url: str = None,
        api_key: str = None,
        api_model: str = None,
    ):
        """
        Args:
            mode: 推理模式 - "local" 本地模型, "api" 远程API（默认从配置读取）
            model_name: 模型路径或 ModelScope 模型ID（默认从配置读取）
            enabled: 是否启用（默认从配置读取）
            batch_size: 批量推理时每批条目数（默认从配置读取）
            max_retries: API 模式下的最大重试次数
            api_base_url: API 接口地址（默认从配置读取）
            api_key: API 密钥（默认从配置读取）
            api_model: API 模型名称（默认从配置读取）

        所有参数均可通过 config/user_config.yaml 的 [llm] 节配置。
        传入参数会覆盖配置文件的值。
        """
        # 从配置文件加载默认值
        cfg = self._load_config()

        self.enabled = enabled if enabled is not None else cfg.get("enabled", False)
        self.mode = mode or cfg.get("mode", "local")
        self.model_name = model_name or cfg.get("model_name", "qwen/Qwen2.5-3B-Instruct")
        self.batch_size = batch_size or cfg.get("batch_size", 20)
        self.max_retries = max_retries
        self.api_base_url = api_base_url or cfg.get("api_base_url", "")
        self.api_key = api_key or cfg.get("api_key", "")
        self.api_model = api_model or cfg.get("api_model", "deepseek-chat")
        self.max_new_tokens = cfg.get("max_new_tokens", 10)
        self.temperature = cfg.get("temperature", 0.1)
        self.device = cfg.get("device", "auto")

        # 判断是否使用本地路径（包含盘符或路径分隔符）
        self._is_local_path = bool(
            re.match(r'^[A-Za-z]:[\\/]', self.model_name) or re.match(r'^[/~]', self.model_name)
        )

        # 模型和分词器（延迟加载）
        self._tokenizer = None
        self._model = None
        self._device = None
        self._load_failed = False  # 加载失败标记，避免重复尝试

        # 分类结果缓存（使用共享 LLMCache）
        self._cache = LLMCache("classify", result_key="c")
        self._cache_enabled = True

        # 模式可用性检查与警告
        if self.mode == "api":
            if not self.api_base_url or not self.api_key:
                logger.warning("LLM API 模式但未配置 api_base_url 或 api_key，分类将降级为关键词方案")
                self.enabled = False
        elif self.mode == "local":
            if not LLM_AVAILABLE:
                missing = []
                if not LLM_TRANSFORMERS_AVAILABLE:
                    missing.append("transformers")
                if not LLM_TORCH_AVAILABLE:
                    missing.append("torch")
                logger.warning(
                    f"LLM 本地模式依赖未安装（缺少: {', '.join(missing)}），"
                    f"分类将降级为关键词方案。安装命令: pip install {' '.join(missing)}"
                )
                self.enabled = False

    @staticmethod
    def _load_config() -> dict:
        """从 user_config.yaml 读取 [llm] 配置节"""
        try:
            from core.config_manager import ConfigManager
            cm = ConfigManager()
            return cm.user_config.get("llm", {})
        except Exception:
            return {}

    # ----------------------------------------------------------
    # 缓存
    # ----------------------------------------------------------

    def _get_cached(self, titles: List[str]) -> Optional[str]:
        """查询缓存，命中则返回分类结果并刷新访问时间"""
        if not self._cache_enabled:
            return None
        return self._cache.get(LLMCache.make_key(*sorted(set(titles))))

    def _put_cache(self, titles: List[str], category: str):
        """写入缓存"""
        if not self._cache_enabled:
            return
        self._cache.put(LLMCache.make_key(*sorted(set(titles))), category)

    # ----------------------------------------------------------
    # 公共接口
    # ----------------------------------------------------------

    def classify(self, title: str, context_titles: List[str] = None) -> str:
        """
        单条分类

        Args:
            title: 主标题
            context_titles: 上下文标题（同一事件的相关话题），用于综合判断

        Returns:
            分类名称字符串
        """
        if not self.enabled:
            return "其他"

        titles = [title] + (context_titles or [])
        combined = "、".join(titles[:5])

        prompt = f"标题：{combined}\n类别："

        result = self._infer_single(prompt)
        return self._parse_type(result)

    def classify_batch(self, title_groups: List[List[str]]) -> List[str]:
        """
        批量分类（推荐使用，效率远高于逐条调用）
        命中缓存的条目直接复用，仅对缓存未命中部分调用 LLM。

        Args:
            title_groups: 标题组列表，每组是一个事件的多个相关标题
                          例如: [["苹果发布新iPhone", "苹果16开售"], ["A股大涨"]]

        Returns:
            与输入等长的分类名称列表
        """
        if not self.enabled or not title_groups:
            return ["其他"] * len(title_groups)

        # 查缓存：区分命中与未命中
        results: List[Optional[str]] = [None] * len(title_groups)
        missed_indices = []
        missed_groups = []

        for i, titles in enumerate(title_groups):
            cached = self._get_cached(titles)
            if cached is not None:
                results[i] = cached
            else:
                missed_indices.append(i)
                missed_groups.append(titles)

        if missed_groups:
            total_miss = len(missed_groups)
            logger.info(f"LLM 分类缓存命中 {len(title_groups) - total_miss}/{len(title_groups)}，"
                        f"需推理 {total_miss} 条")

            # 仅对未命中部分调用 LLM
            miss_results = []
            for i in range(0, total_miss, self.batch_size):
                batch = missed_groups[i:i + self.batch_size]
                batch_results = self._infer_batch(batch)
                miss_results.extend(batch_results)

                done = min(i + self.batch_size, total_miss)
                logger.info(f"LLM 分类进度: {done}/{total_miss}")

            # 写回结果并更新缓存
            for idx, (orig_i, titles) in enumerate(zip(missed_indices, missed_groups)):
                cat = miss_results[idx]
                results[orig_i] = cat
                self._put_cache(titles, cat)

            # 持久化缓存
            self._cache.save()
        else:
            logger.info(f"LLM 分类全部命中缓存 ({len(title_groups)} 条)，无需推理")

        return results  # type: ignore[return-value]

    def classify_events(self, events: list) -> Dict[str, Tuple[str, float]]:
        """
        事件级分类（直接处理事件对象列表）

        Args:
            events: EventInfoEnhanced 对象列表

        Returns:
            {event_id: (category_name, confidence)} 字典
        """
        if not self.enabled or not events:
            return {}

        title_groups = []
        event_ids = []

        for event in events:
            # 优先只用事件主标题，避免被聚类中混入的不相关话题带偏
            titles = [event.title]
            # 仅当主标题过短（≤4字，信息量不足）时，补充同事件的高热度关联标题
            if len(event.title) <= 4 and event.topics:
                extra = [t.title for t in event.topics[:3] if t.title != event.title]
                titles.extend(extra)
            title_groups.append(titles[:5])
            event_ids.append(event.event_id)

        types = self.classify_batch(title_groups)

        result = {}
        for eid, et in zip(event_ids, types):
            confidence = 0.85 if et != "其他" else 0.5
            result[eid] = (et, confidence)

        return result

    # ----------------------------------------------------------
    # 推理引擎
    # ----------------------------------------------------------

    def _infer_raw(self, system_prompt: str, user_prompt: str,
                   max_tokens: int = 10) -> str:
        """
        统一推理入口：本地模型或 API 调用。
        供 classify 内部使用，也可被 LLMInference（llm_middleware）外部调用。
        """
        if self.mode == "api" and self.api_base_url:
            return self._infer_api(system_prompt, user_prompt, max_tokens)
        return self._infer_local(system_prompt, user_prompt, max_tokens)

    def _infer_local(self, system_prompt: str, user_prompt: str,
                     max_tokens: int) -> str:
        """本地模型推理"""
        if not self._ensure_model_loaded():
            return ""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            text = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self._tokenizer([text], return_tensors="pt").to(self._device)

            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=self.temperature,
                    top_p=0.9,
                    do_sample=False,
                    pad_token_id=self._tokenizer.eos_token_id,
                )

            response = self._tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
            ).strip()
            return response

        except Exception as e:
            logger.error(f"LLM 本地推理失败: {e}")
            return ""

    def _infer_api(self, system_prompt: str, user_prompt: str,
                   max_tokens: int) -> str:
        """API 推理（单条）"""
        try:
            import requests
        except ImportError:
            logger.error("API 模式需要 requests 库")
            return ""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.api_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    f"{self.api_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"API 推理失败（已重试{self.max_retries}次）: {e}")
                    return ""
                wait = 2 ** attempt  # 指数退避: 1s, 2s, 4s
                logger.warning(f"API 请求失败，{wait}秒后重试({attempt+1}/{self.max_retries}): {e}")
                time.sleep(wait)
        return ""

    def _infer_api_batch(self, system_prompt: str, prompts: List[str],
                         max_tokens: int = 10) -> List[str]:
        """
        API 批量推理：将多条 prompt 打包为一条请求，减少 API 调用次数和 token 消耗。

        将 N 条独立请求（每条都重复 system_prompt）合并为 1 条请求，
        只发送一次 system_prompt + 一条包含所有任务的 user_prompt。
        返回与 prompts 等长的结果列表。
        """
        if not prompts:
            return []

        # 单条直接走原有逻辑
        if len(prompts) == 1:
            result = self._infer_api(system_prompt, prompts[0], max_tokens)
            return [result] if result else [""]

        # 构建批量 user_prompt
        lines = []
        for i, p in enumerate(prompts, 1):
            # 去掉原始 prompt 中可能的前缀
            text = p.strip()
            text = re.sub(r'^标题[：:]\s*', '', text)
            text = re.sub(r'类别[：:]\s*$', '', text)
            lines.append(f"{i}. 标题：{text}")

        batch_prompt = BATCH_CLASSIFY_PROMPT.format(
            count=len(prompts),
            items="\n".join(lines) + "\n类别（每行一个，顺序对应）："
        )

        try:
            import requests
        except ImportError:
            return [""] * len(prompts)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.api_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": batch_prompt},
            ],
            "max_tokens": max_tokens * len(prompts) + 50,
            "temperature": 0.1,
        }

        # 超时随批量大小动态调整
        timeout = max(60, 30 * (len(prompts) // 10 + 1))

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    f"{self.api_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()

                # 按行拆分结果，与输入顺序对应
                result_lines = []
                for line in content.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    # 去除行号前缀（如 "1. 科技" → "科技"）
                    line = re.sub(r'^\d+\s*[.、:：)\]】]\s*', '', line)
                    if line:
                        result_lines.append(line)

                # 补齐或截断到与输入等长
                while len(result_lines) < len(prompts):
                    result_lines.append("")
                results = result_lines[:len(prompts)]

                logger.debug(f"API 批量推理: {len(prompts)} 条打包发送")
                return results

            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"API 批量推理失败（已重试{self.max_retries}次）: {e}")
                    return [""] * len(prompts)
                wait = 2 ** attempt
                logger.warning(f"API 批量请求失败，{wait}秒后重试({attempt+1}/{self.max_retries}): {e}")
                time.sleep(wait)
        return [""] * len(prompts)

    def _infer_single(self, prompt: str) -> str:
        """单条分类推理（使用固定 SYSTEM_PROMPT）"""
        result = self._infer_raw(SYSTEM_PROMPT, prompt, max_tokens=self.max_new_tokens)
        return result if result else "其他"

    def _infer_batch(self, title_groups: List[List[str]]) -> List[EventType]:
        """
        批量推理

        API 模式：将多个标题打包为一条请求，只发一次 system_prompt，
        大幅减少 API 调用次数和 token 消耗。
        本地模式：逐条推理。
        """
        if self.mode == "api" and self.api_base_url:
            return self._infer_batch_api(title_groups)

        # 本地模式：逐条推理
        results = []
        for titles in title_groups:
            combined = "、".join(titles[:5])
            prompt = f"标题：{combined}\n类别："
            response = self._infer_raw(SYSTEM_PROMPT, prompt, max_tokens=self.max_new_tokens)
            results.append(self._parse_type(response) if response else "其他")
        return results

    def _infer_batch_api(self, title_groups: List[List[str]]) -> List[str]:
        """
        API 模式下的真正批量推理

        将 batch_size 条标题打包为一条请求发送，相比逐条调用：
        - API 调用次数从 N 降低到 ceil(N/batch_size)
        - system_prompt 只发送一次（而非 N 次）
        """
        results = []
        for i in range(0, len(title_groups), self.batch_size):
            batch = title_groups[i:i + self.batch_size]
            prompts = []
            for titles in batch:
                combined = "、".join(titles[:5])
                prompts.append(f"标题：{combined}\n类别：")

            batch_results = self._infer_api_batch(SYSTEM_PROMPT, prompts,
                                                   max_tokens=self.max_new_tokens)
            for response in batch_results:
                results.append(self._parse_type(response) if response else "其他")

        return results

    # ----------------------------------------------------------
    # 模型加载
    # ----------------------------------------------------------

    def _resolve_device(self) -> str:
        """根据配置和硬件环境确定推理设备"""
        dev = self.device.lower().strip()
        if dev == "cuda":
            if torch.cuda.is_available():
                return "cuda"
            logger.warning("配置要求 GPU (cuda) 但 CUDA 不可用，回退到 CPU")
            return "cpu"
        if dev == "cpu":
            return "cpu"
        # auto: 优先 GPU
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _ensure_model_loaded(self) -> bool:
        """确保模型已加载（首次调用时加载，后续复用）"""
        if self.mode == "api":
            return bool(self.api_base_url and self.api_key)

        if self._model is not None:
            return True

        if self._load_failed:
            return False

        try:
            model_path = self.model_name

            # ModelScope 模型ID：先下载到本地缓存，再从缓存加载
            if not self._is_local_path:
                model_path = self._download_from_modelscope(self.model_name)
                if model_path is None:
                    self._load_failed = True
                    return False

            logger.info(f"正在加载 LLM 模型: {model_path}")

            self._device = self._resolve_device()
            logger.info(f"推理设备: {self._device}")

            self._tokenizer = AutoTokenizer.from_pretrained(
                model_path, trust_remote_code=True
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype="auto",
                trust_remote_code=True,
            ).to(self._device)
            self._model.eval()

            logger.info(f"模型加载完成: {self.model_name} @ {self._device}")
            return True

        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            logger.error("LLM 分类将降级为关键词方案")
            self._load_failed = True
            return False

    def _download_from_modelscope(self, model_id: str) -> Optional[str]:
        """
        从 ModelScope 下载模型到本地缓存，返回本地路径。

        Args:
            model_id: ModelScope 模型ID，如 "qwen/Qwen2.5-3B-Instruct"

        Returns:
            本地路径字符串，失败时返回 None
        """
        try:
            from modelscope import snapshot_download
        except ImportError:
            logger.error(
                "ModelScope 未安装，无法下载模型。请执行: pip install modelscope"
            )
            self.enabled = False
            return None

        try:
            # ModelScope 缓存目录：项目根目录下 .model_cache
            cache_dir = Path(__file__).parent.parent / ".model_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # 先检查本地缓存是否已存在（snapshot_download 会把 . 替换为 ___）
            # 模型ID "qwen/Qwen2.5-3B-Instruct" → 缓存路径含 "Qwen2___5-3B-Instruct"
            cached_name = model_id.split("/")[-1].replace(".", "___") if "/" in model_id else model_id.replace(".", "___")
            cached_model_dir = cache_dir / model_id.split("/")[0] / cached_name

            if cached_model_dir.is_dir():
                logger.info(f"检测到本地缓存: {cached_model_dir}")
                return str(cached_model_dir)

            logger.info(f"正在从 ModelScope 下载模型: {model_id}（缓存至 {cache_dir}）")
            logger.info("首次下载可能需要几分钟，后续会自动使用缓存")

            local_path = snapshot_download(
                model_id=model_id,
                cache_dir=str(cache_dir),
            )
            logger.info(f"模型下载完成: {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"ModelScope 下载失败: {e}")
            logger.error("LLM 分类将降级为关键词方案")
            self.enabled = False
            return None

    # ----------------------------------------------------------
    # 结果解析
    # ----------------------------------------------------------

    def _parse_type(self, response: str) -> str:
        """
        解析模型输出为分类名称字符串

        模型可能返回: "科技"、"科技。"、"类别：科技" 等各种格式
        """
        # 清理响应文本
        text = response.strip().rstrip("。.！!，,")
        # 去除可能的前缀
        text = re.sub(r'^(类别[:：]|类型[:：])\s*', '', text)

        # 清除引号包裹（英文和中文引号）
        text = text.strip('"\'「」\u201c\u201d\u2018\u2019')

        if not text or len(text) > 10:
            logger.debug(f"LLM 响应异常: '{response}'，默认返回'其他'")
            return "其他"

        # 别名归一化：将同义类别名映射到标准类别
        return _CATEGORY_ALIASES.get(text, text)

    # ----------------------------------------------------------
    # 状态查询
    # ----------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """分类器是否可用"""
        if not self.enabled:
            return False
        if self.mode == "api":
            return bool(self.api_base_url and self.api_key)
        if self.mode == "local":
            return LLM_AVAILABLE
        return False

    @property
    def status(self) -> dict:
        """返回分类器状态信息"""
        cache_stats = self._cache.stats()
        return {
            "enabled": self.enabled,
            "available": self.is_available,
            "mode": self.mode,
            "model_name": self.model_name,
            "device": str(self._device) if self._device else "未加载",
            "model_loaded": self._model is not None,
            "cache_enabled": self._cache_enabled,
            "cache_size": cache_stats["size"],
            "cache_file": cache_stats["file"],
        }


# ============================================================
# 模块级便捷函数
# ============================================================

# 全局分类器实例（延迟初始化）
_classifier_instance: Optional[LLMEventClassifier] = None


def get_classifier() -> Optional[LLMEventClassifier]:
    """获取全局分类器实例（未配置时返回 None）"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = LLMEventClassifier()
    return _classifier_instance if _classifier_instance.enabled else None




