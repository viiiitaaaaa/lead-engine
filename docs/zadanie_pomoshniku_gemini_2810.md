# Task for helper: generate 9 photos in Gemini (28.10.2026)

Goal: generate 9 documentary-style photos in Gemini and save them as files.
Prompts: C:\Users\User\lead-engine\docs\promty_kartinok_foto_2810.html (blocks hero1..hero5, dir1..dir4; the second paragraph of each block is the full prompt — use the FULL one).
Gemini: gemini.google.com/u/0 (working account, Pro). Do NOT use /u/2. Open ONLY in the extension's tab group; do not create extra tabs.
Method: new chat per image batch; insert prompt with execCommand('insertText') into div[contenteditable]; press Enter; wait ~30 s; click the "download" icon on the image; file appears in C:\Users\User\Downloads\Gemini_Generated_Image_*.jfif in 10-15 s.
Files to change: only copy results to C:\Users\User\lead-engine\site\img\new\<key>.jpg (hero1..hero5, dir1..dir4). Do not touch other files. Do NOT run build.py, do NOT commit.
Sample of one-line result: `hero2 | ok | 2912x1440 | img\new\hero2.jpg`
If A (image has people, text, logo, purple tint or looks like a render) — then regenerate once with "photo, not a render, neutral colours" added; still bad — mark `bad` and go on.
If B (Gemini error "Что-то пошло не так") — retry max 3 times with pauses, then stop and report.
Step ceiling: no more than 80 actions; stuck — stop and report. Same action 3 times without new info — stop.
Old hero1 (purple tint, identical to Downloads\Gemini_Generated_Image_om95xoom95xoom95.jfif) must be REPLACED by the new one, keep old as img\new\hero1_old.jpg.
Final reply to me: the table of 9 lines above, in Russian.
