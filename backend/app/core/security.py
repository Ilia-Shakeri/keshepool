import hashlib
import hmac
import urllib.parse
from fastapi import HTTPException, Header
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

def validate_telegram_data(init_data: str = Header(..., alias="X-Telegram-Init-Data")):
    """
    Validates the data received from the Telegram Web App to prevent spoofing.
    Implements the official Telegram validation algorithm.
    """
    parsed_data = dict(urllib.parse.parse_qsl(init_data))
    
    if "hash" not in parsed_data:
        raise HTTPException(status_code=401, detail="Missing hash parameter.")
        
    received_hash = parsed_data.pop("hash")
    
    # Sort the data alphabetically
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed_data.items())
    )
    
    # Generate the secret key using the bot token
    secret_key = hmac.new("WebAppData".encode(), BOT_TOKEN.encode(), hashlib.sha256).digest()
    
    # Calculate the hash
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if calculated_hash != received_hash:
        raise HTTPException(status_code=403, detail="Invalid Telegram signature.")
        
    return parsed_data