import sys
import os

sys.path.append(os.getcwd())
from pipeline.image_generator import generate_sticker_image

res = generate_sticker_image(
    "cute cartoon cat on a birthday cake", "debug_session", "output/debug"
)
print(f"Final Path: {res}")
if "debug_session_sticker.png" in res:
    print("Success: Generated a real file path.")
else:
    print("Failure: Returned placeholder or error path.")
