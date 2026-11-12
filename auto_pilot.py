
import time

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

def _get_status_code(error):
    for attribute in ("code", "status_code", "http_status"):
        value = getattr(error, attribute, None)

        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass

    message = str(error)

    for code in RETRYABLE_STATUS_CODES:
        if str(code) in message:
            return code

    return None

def generate_with_autopilot(client, model, contents, backup_func=None):

    for attempt in range(2):
        try:
            print(f"NEXTGEN: Gemini attempt {attempt + 1}/2")

            response = client.models.generate_content(
                model=model,
                contents=contents
            )

            answer = response.text

            if answer and answer.strip():
                return answer, "Gemini"

            raise RuntimeError("Gemini returned an empty response.")

        except Exception as error:
            status_code = _get_status_code(error)

            print(f"Gemini Error: {error}")

            if status_code not in RETRYABLE_STATUS_CODES:
                break

            if attempt == 0:
                time.sleep(1)

    if backup_func is not None:
        try:
            backup_answer = backup_func(contents)

            if backup_answer and backup_answer.strip():
                return backup_answer, "Backup AI"
        except Exception as error:
            print(f"Backup AI Error: {error}")
   print("FINAL GEMINI STATUS:", status_code)
    raise RuntimeError(
        "AI is temporarily unavailable. Please try again."
    )
