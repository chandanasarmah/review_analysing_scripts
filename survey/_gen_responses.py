import csv
try:
    from openpyxl import Workbook
    HAVE_XLSX = True
except ImportError:
    HAVE_XLSX = False

headers = [
 "Timestamp",
 "How long have you used Spotify?",
 "What plan are you currently on?",
 "How often do you listen to Spotify?",
 "Which best describes how you usually start listening?",
 "Which Spotify features do you regularly use?",
 "Have you ever cancelled Premium or seriously considered leaving Spotify?",
 "If you left or considered leaving, where did you go (or consider going)?",
 "How satisfied are you with how Spotify helps you discover new music?",
 "How often do you find genuinely new artists or songs you love through Spotify?",
 "What gets in the way of discovering new music? (select all that apply)",
 "Describe a time Spotify recommended something that worked really well — or really didn't.",
 "How often does it feel like Spotify plays the same songs over and over?",
 "When does repetition bother you most? (select all that apply)",
 "I feel in control of what plays next.",
 "Spotify's recommendations match my taste.",
 'I feel Spotify keeps me in a "bubble" of very similar music.',
 "What frustrates you most about recommendations? (select all that apply)",
 "In which situations do you mainly listen? (select all that apply)",
 "In those moments, what are you mainly trying to get from Spotify?",
 "How well does Spotify serve your main listening situation?",
 "How disruptive are ads to your listening?",
 "Which features do you most wish Spotify had — or brought back? (select all that apply)",
 "What is the single biggest thing Spotify could fix or add for you?",
 "How likely are you to recommend Spotify to a friend?",
 "Anything else you'd like to tell us about your Spotify experience?",
]

rows = [
 ["6/27/2026 18:42:11","More than 3 years","Free (with ads)","Multiple times a day",
  "I search for and pick specific songs, artists, or playlists",
  "Liked Songs / your own library, Playlists you created, Autoplay / Radio",
  "Yes — I seriously considered it","Apple Music","2","Rarely",
  "Recommendations feel repetitive, Too much focus on what I already listen to",
  "An ad cuts in every two or three songs and completely breaks my focus while studying.",
  "4","On shuffle, In autoplay / radio","2","2","4",
  "Too repetitive, I can't influence or reset them",
  "Focus / work / study, Commute / driving, Relaxing / sleep / background",
  "Background music that doesn't break my concentration.","2",
  "So disruptive it makes me consider leaving",
  'Fewer / shorter ads on free tier, More control over recommendations, Truly random ("real") shuffle',
  "Cut the ads down and stop replaying the same twenty songs.","3",
  "I'd pay for Premium if it were cheaper in my region."],

 ["6/27/2026 19:05:33","More than 3 years","Premium Individual","Multiple times a day",
  "A roughly even mix of both",
  "Discover Weekly, Release Radar, Daily Mix, Wrapped, Blend, Liked Songs / your own library",
  "No","Not applicable","5","Often","I don't have trouble discovering music",
  "Discover Weekly introduced me to my now-favourite indie band — completely spot on.",
  "2","Repetition doesn't bother me","5","5","2","Nothing — they work well for me",
  "Focus / work / study, Mood or emotional listening, Social settings / parties",
  "A soundtrack for every part of my day.","5","I'm on Premium — no ads",
  "Lyrics improvements, Higher-quality / hi-fi audio",
  "A true hi-fi tier and a smarter AI DJ that actually reads my mood.","10",
  "Wrapped every year is the highlight — I love it."],

 ["6/27/2026 20:11:47","I no longer use it","I cancelled / no longer subscribe","Rarely / occasionally",
  "I search for and pick specific songs, artists, or playlists","Liked Songs / your own library",
  "Yes — I cancelled / stopped using it","YouTube Music","3","Sometimes",
  "Suggestions don't match my taste, Too much focus on what I already listen to",
  "It kept pushing mainstream pop when I was clearly trying to find obscure jazz.",
  "4","In algorithmic playlists (e.g. Daily Mix)","3","2","5",
  "Ignores my mood or context, I can't influence or reset them",
  "Commute / driving, Relaxing / sleep / background","Calm music to wind down to.","2",
  "So disruptive it makes me consider leaving",
  "Cheaper or more flexible plans, More control over recommendations",
  "YouTube Music gives me videos too and is cheaper — Spotify needs better value.","4",
  "I might come back if the pricing and recommendations improved."],

 ["6/27/2026 21:30:02","1–6 months","Free (with ads)","A few times a week",
  "I search for and pick specific songs, artists, or playlists","Liked Songs / your own library",
  "No","Not applicable","3","Sometimes","Discovery features are hard to find or navigate",
  "Still figuring it out — the home screen feels a bit cluttered for a beginner.",
  "2","Repetition doesn't bother me","3","3","2","Nothing — they work well for me",
  "Relaxing / sleep / background, Mood or emotional listening","Something chill while I unwind.","3",
  "Somewhat disruptive","Better search and filtering, Fewer / shorter ads on free tier",
  "Make it easier to find good playlists when you're new.","7",
  "Only just started — seems good so far."],

 ["6/27/2026 22:14:55","1–3 years","Premium Student","Multiple times a day",
  "I let autoplay, radio, or shuffle decide","Daily Mix, Autoplay / Radio",
  "No","Not applicable","3","Sometimes","Recommendations feel repetitive",
  "I just hit play on a Daily Mix and let it run in the background all day.",
  "5","On shuffle, In autoplay / radio, In algorithmic playlists (e.g. Daily Mix)","2","3","4",
  "Too repetitive, Ignores my mood or context",
  "Focus / work / study, Workout / exercise, Commute / driving",
  "Set it and forget it — a constant background flow.","4","I'm on Premium — no ads",
  'Truly random ("real") shuffle, More control over recommendations',
  "Shuffle that's actually random and radio that doesn't loop the same tracks.","7",
  "I rarely pick songs myself, so the algorithm really matters to me."],

 ["6/28/2026 08:47:19","1–3 years","Premium Student","About once a day",
  "A roughly even mix of both",
  "Discover Weekly, Liked Songs / your own library, Playlists you created",
  "Yes — I seriously considered it","YouTube Music","3","Sometimes",
  "Recommendations feel repetitive, Too much focus on what I already listen to",
  "Recommendations are okay, but I worry about the price once my student plan ends.",
  "3","On shuffle","4","3","3","Too repetitive",
  "Focus / work / study, Commute / driving","Focus music during study sessions.","4",
  "I'm on Premium — no ads","Cheaper or more flexible plans, Better search and filtering",
  "Keep student pricing affordable even after I graduate.","7",
  "I'll probably switch if the price jumps a lot."],

 ["6/28/2026 09:33:40","6 months – 1 year","Free (with ads)","Multiple times a day",
  "I search for and pick specific songs, artists, or playlists",
  "Liked Songs / your own library, Playlists you created, Autoplay / Radio",
  "Yes — I seriously considered it","YouTube Music","2","Rarely",
  "Recommendations feel repetitive, Suggestions don't match my taste",
  "An ad blasted at full volume mid-workout and completely killed my momentum.",
  "4","On shuffle, In autoplay / radio","2","2","4",
  "Too repetitive, I can't influence or reset them",
  "Workout / exercise, Commute / driving","High-energy tracks to keep me going at the gym.","2",
  "So disruptive it makes me consider leaving",
  'Fewer / shorter ads on free tier, More control over recommendations, Truly random ("real") shuffle',
  "Let me skip more songs and cut the ads during workouts.","3",
  "The free tier is basically unusable mid-exercise."],

 ["6/28/2026 10:18:27","More than 3 years","Premium Individual","Multiple times a day",
  "I search for and pick specific songs, artists, or playlists",
  "Blend, Liked Songs / your own library, Playlists you created",
  "No","Not applicable","4","Sometimes","Too much focus on what I already listen to",
  "Blend with my partner is great — it found songs we both love.",
  "3","In autoplay / radio","4","4","3","I can't influence or reset them",
  "Focus / work / study, Relaxing / sleep / background","Steady focus music for deep work.","4",
  "I'm on Premium — no ads","Better queue control, More control over recommendations",
  "Let me reset my recommendations and nudge me out of my bubble now and then.","8",
  "Mostly happy — I just want more genuinely new music."],

 ["6/28/2026 11:52:09","1–3 years","Premium Individual","Multiple times a day",
  "A roughly even mix of both",
  "Discover Weekly, Daily Mix, Liked Songs / your own library, Playlists you created",
  "No","Not applicable","2","Rarely",
  "Recommendations feel repetitive, Too much focus on what I already listen to",
  "I hide songs but they keep reappearing in other mixes — I can't escape the loop.",
  "5","In autoplay / radio, In algorithmic playlists (e.g. Daily Mix)","2","2","5",
  "Too repetitive, Ignores my mood or context, I can't influence or reset them",
  "Focus / work / study, Workout / exercise, Commute / driving, Mood or emotional listening",
  "Music that matches my energy and mood.","3","I'm on Premium — no ads",
  'Better queue control, More control over recommendations, Truly random ("real") shuffle',
  "A way to truly refresh my recommendations and break out of the bubble.","6",
  "Love the catalogue, but I hate feeling stuck in a rut."],

 ["6/28/2026 13:07:51","More than 3 years","Premium Duo or Family","About once a day",
  "I search for and pick specific songs, artists, or playlists",
  "Wrapped, Liked Songs / your own library, Playlists you created",
  "No","Not applicable","4","Sometimes","I don't have trouble discovering music",
  "Found great playlists for road trips that the whole family enjoys.",
  "2","Repetition doesn't bother me","4","4","2","Nothing — they work well for me",
  "Commute / driving, Relaxing / sleep / background, Social settings / parties",
  "Easy listening that everyone in the car enjoys.","5","I'm on Premium — no ads",
  "Lyrics improvements, Cheaper or more flexible plans",
  "Maybe a cheaper add-on slot for extra family members.","9",
  "The family plan is great value for us."],
]

for i, r in enumerate(rows, 1):
    assert len(r) == len(headers), f"row {i} has {len(r)} cols, expected {len(headers)}"

csv_path = "survey/synthetic_10_responses.csv"
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(headers)
    w.writerows(rows)
print("wrote", csv_path)

if HAVE_XLSX:
    wb = Workbook(); ws = wb.active; ws.title = "Responses"
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save("survey/synthetic_10_responses.xlsx")
    print("wrote survey/synthetic_10_responses.xlsx")
else:
    print("openpyxl not installed - CSV only")
