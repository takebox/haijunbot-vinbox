import sys
sys.path.insert(0, "/app/vinbox/HaijunBot/src")
from haijunbot.vinbox_bridge import ask
import time
t = time.time()
r = ask("Balas satu kata: siap", non_interactive=True)
print("RESULT:", repr(r)[:500])
print("TIME:", round(time.time() - t, 1))
EOF