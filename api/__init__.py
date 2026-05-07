"""
API 应用模块
Flask 应用工厂 + Blueprint 注册 + 服务器启动
"""

from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from core.service import get_service
from core.logger import get_logger
from .helpers import success_response, error_response

logger = get_logger(__name__)


def create_app() -> Flask:
    """
    Flask 应用工厂。
    所有 Blueprint 在此处统一注册，方便后续扩展。
    """
    app = Flask(__name__,
                static_folder=str(Path(__file__).parent.parent / 'static'),
                static_url_path='/static')
    CORS(app)

    # ---- 注册 Blueprint ----
    from .routes.operations import bp as operations_bp
    from .routes.scheduler import bp as scheduler_bp
    from .routes.platforms import bp as platforms_bp
    from .routes.configs import bp as configs_bp
    from .routes.outputs import bp as outputs_bp
    from .routes.logs import bp as logs_bp

    app.register_blueprint(operations_bp, url_prefix='/api')
    app.register_blueprint(scheduler_bp, url_prefix='/api/scheduler')
    app.register_blueprint(platforms_bp, url_prefix='/api/platforms')
    app.register_blueprint(configs_bp, url_prefix='/api/config-files')
    app.register_blueprint(outputs_bp, url_prefix='/api/outputs')
    app.register_blueprint(logs_bp, url_prefix='/api/logs')

    # ---- 顶层路由（不属于任何 Blueprint） ----

    @app.route('/')
    def index():
        """GUI 管理界面"""
        gui_path = Path(__file__).parent.parent / 'templates' / 'gui.html'
        if gui_path.exists():
            return send_file(str(gui_path))
        return '<h1>GUI template not found</h1><p>templates/gui.html does not exist.</p>'

    @app.route('/api/health', methods=['GET'])
    def health_check():
        """健康检查"""
        return jsonify(success_response({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        }))

    @app.route('/api/status', methods=['GET'])
    def get_status():
        """获取服务状态"""
        try:
            service = get_service()
            api_key = service.config.get('service', {}).get('api_key', '')
            if api_key:
                req_key = request.headers.get('X-API-Key') or request.args.get('api_key')
                if req_key != api_key:
                    return jsonify(error_response("Invalid API key", 401)), 401

            status = service.get_status()
            status['platforms'] = {
                'available': service.crawler_factory.get_available_platforms(),
                'total': len(service.crawler_factory.get_available_platforms()),
            }
            return jsonify(success_response(status))
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return jsonify(error_response(str(e))), 500

    # ---- 错误处理 ----

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(error_response("Endpoint not found", 404)), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify(error_response("Internal server error", 500)), 500

    return app


# ==================== 便捷入口（兼容旧代码） ====================

_default_app = None


def get_app() -> Flask:
    """获取或创建默认 Flask 实例"""
    global _default_app
    if _default_app is None:
        _default_app = create_app()
    return _default_app


def run_api_server(host: str = '0.0.0.0', port: int = None, debug: bool = False):
    """
    启动 API 服务器

    Args:
        host: 绑定地址
        port: 端口号，为空则从配置读取
        debug: 调试模式
    """
    service = get_service()
    config_port = service.config.get('service', {}).get('port', 5000)

    if port is None:
        port = config_port

    logger.info(f"启动API服务器: http://{host}:{port}")
    get_app().run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_api_server()
