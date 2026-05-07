"""GPU 可用性检测脚本"""
import sys

print("=" * 50)
print("GPU / CUDA 环境检测")
print("=" * 50)

# 1. Python 版本
print(f"\nPython 版本: {sys.version}")

# 2. PyTorch 检测
try:
    import torch
    print(f"\nPyTorch 版本: {torch.__version__}")
    print(f"CUDA 编译版本: {torch.version.cuda}")
    print(f"cuDNN 版本: {torch.backends.cudnn.version()}")
    print(f"CUDA 是否可用: {'是' if torch.cuda.is_available() else '否'}")
except ImportError:
    print("\nPyTorch 未安装！请执行: pip install torch")
    sys.exit(1)

# 3. GPU 信息
if torch.cuda.is_available():
    print(f"\nGPU 数量: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        print(f"\n  GPU [{i}]: {props.name}")
        print(f"    显存: {props.total_memory / 1024**3:.1f} GB")
        print(f"    计算能力: {props.major}.{props.minor}")
    # 简单推理测试
    print("\n正在进行简单 GPU 推理测试...")
    try:
        x = torch.randn(1000, 1000).cuda()
        y = torch.matmul(x, x)
        torch.cuda.synchronize()
        print("  GPU 推理测试: 通过")
    except Exception as e:
        print(f"  GPU 推理测试: 失败 ({e})")
else:
    print("\n未检测到可用的 CUDA GPU！")
    print("可能原因:")
    print("  1. 未安装 NVIDIA 显卡驱动")
    print("  2. 安装了 CPU 版 PyTorch（需要 CUDA 版本）")
    print("  3. PyTorch CUDA 版本与显卡驱动不匹配")
    print("\n解决方法:")
    print("  访问 https://pytorch.org 获取对应 CUDA 版本的安装命令")
    print("  例如: pip install torch --index-url https://download.pytorch.org/whl/cu121")

print("\n" + "=" * 50)
