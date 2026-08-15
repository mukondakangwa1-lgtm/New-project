from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi.limiter import FastAPILimiter
from fastapi.limiter.depends import RateLimiter

# Define a simple rate limiter in memory for simplicity
# In production, use Redis.
class SimpleRateLimiter:
    def __init__(self, requests: int, seconds: int):
        self.requests = requests
        self.seconds = seconds
        self.history = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = datetime.utcnow()
        self.history[user_id] = [t for t in self.history[user_id] if now - t < timedelta(seconds=self.seconds)]
        if len(self.history[user_id]) >= self.requests:
            return False
        self.history[user_id].append(now)
        return True

# 5 messages per 10 seconds
chat_limiter = SimpleRateLimiter(5, 10)
MAX_MESSAGE_LENGTH = 1000
