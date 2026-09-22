# B F Futa — drop-in debug overlay

Copy `bf_futa.py` into any Tk/Python desktop app.

```python
import bf_futa
bf = bf_futa.install(root, "MyApp")
bf.attach_checkbox(settings_frame)   # dummy checkbox, looks inert
bf.log("error", "copy", "COPY FAIL", "disk full", "AB: robocopy vs shutil", dest="E:\\")
```

**Unlock:** click the checkbox there-and-back **3 times** (6 clicks) within **5 seconds**.
One click does nothing. One click while the window is open **closes** it.

**Levels:** `error` red · `warn` yellow · `info` white · `sys` gray.

Click a line → square popup (1/6 of screen), copy icon, OK.

Do not persist the checkbox. It is not a real setting.
