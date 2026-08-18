from pydantic import BaseModel

class KudosChatRequest(BaseModel):
    message: str
    sessionId: str
