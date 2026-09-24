from routers.system_routes import router as system_router
from routers.auth_routes import router as auth_router
from routers.document_routes import router as document_router
from routers.conversation_routes import router as conversation_router
from routers.chat_routes import router as chat_router
from routers.rag_routes import router as rag_router
from routers.analytics_routes import router as analytics_router
from routers.feedback_routes import router as feedback_router
from routers.cache_routes import router as cache_router

__all__ = [
    "system_router",
    "auth_router",
    "document_router",
    "conversation_router",
    "chat_router",
    "rag_router",
    "analytics_router",
    "feedback_router",
    "cache_router",
]
