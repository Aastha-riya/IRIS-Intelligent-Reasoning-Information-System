events = container.get("events")
logger = Logger()

events.subscribe(
    "user_message",
    lambda text: logger.log(f"USER : {text}")
)

events.subscribe(
    "assistant_message",
    lambda text: logger.log(f"IRIS : {text}")
)