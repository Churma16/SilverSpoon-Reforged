import re

def format_error_message(error, max_length=160):
    text = str(error).strip()
    lower_text = text.lower()
    error_type = type(error).__name__

    if "connectionabortederror" in lower_text or "10053" in text:
        return "Connection was aborted by your computer or network security software. Try again, or check firewall/antivirus settings."
    if "connection reset" in lower_text or "connectionreseterror" in lower_text:
        return "Connection was reset by the server or your network. Try again later."
    if "timed out" in lower_text or "timeout" in lower_text:
        return "The connection timed out. Check your network and try again."

    if not text:
        return error_type

    text = re.sub(r"\s+", " ", text)
    if len(text) > max_length:
        text = text[:max_length].rstrip() + "..."
    return f"{error_type}: {text}"
