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

    wait_times = (2, 4)

    for attempt in range(3):

        try:
            print(
                f"NEXTGEN AUTO-PILOT: Gemini attempt {attempt + 1}/3"
            )

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

            print(f"NEXTGEN AUTO-PILOT ERROR: {error}")

            if status_code not in RETRYABLE_STATUS_CODES:
                raise

            if attempt < 2:
                wait_seconds = wait_times[attempt]

                print(
                    f"Retrying in {wait_seconds} seconds..."
                )

                time.sleep(wait_seconds)

    if backup_func is not None:

        backup_answer = backup_func(contents)

        if backup_answer and backup_answer.strip():
            return backup_answer, "Backup AI"

    raise RuntimeError(
        "Gemini is temporarily unavailable after 3 attempts. "
        "No backup provider is configured yet."
    )