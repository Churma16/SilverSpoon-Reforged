import os
import json
import urllib.request
import urllib.error


def dispatch_canary_failure_alert():
    bot_token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHAT_ID")
    run_url = os.environ.get("RUN_URL", "")
    repository_name = os.environ.get("GITHUB_REPOSITORY", "Churma16/SilverSpoon-Reforged")

    if not bot_token or not chat_id:
        print("Telegram credentials (BOT_TOKEN / CHAT_ID) are not configured. Skipping alert.")
        return

    summary_file_path = "canary_error_summary.txt"
    if os.path.exists(summary_file_path):
        try:
            with open(summary_file_path, "r", encoding="utf-8") as summary_file:
                summary_content = summary_file.read().strip()
        except Exception as read_error:
            summary_content = f"<b>Reason:</b>\nFailed reading error summary file: {read_error}"
    else:
        summary_content = (
            "<b>Reason:</b>\n"
            "Live link extraction probe failed without generating a detailed summary. "
            "The file host service may have updated their download page structure or challenge layout."
        )

    alert_message = (
        "<b>[ALERT] SilverSpoon Link Resolver Failed!</b>\n\n"
        f"{summary_content}\n\n"
        f"<b>Repository:</b> {repository_name}\n"
        f"<b>Action Run:</b> <a href=\"{run_url}\">View Run Log</a>"
    )

    telegram_endpoint_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    request_payload_bytes = json.dumps({
        "chat_id": chat_id,
        "text": alert_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    telegram_request = urllib.request.Request(
        telegram_endpoint_url,
        data=request_payload_bytes,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(telegram_request, timeout=15) as response:
            response_data = response.read().decode("utf-8")
            print("Telegram alert sent successfully:", response_data)
    except urllib.error.HTTPError as http_error:
        error_response_body = http_error.read().decode("utf-8", errors="ignore")
        print(f"Failed sending Telegram alert. HTTP {http_error.code}: {error_response_body}")
    except Exception as network_error:
        print(f"Failed sending Telegram alert due to network exception: {network_error}")


if __name__ == "__main__":
    dispatch_canary_failure_alert()
