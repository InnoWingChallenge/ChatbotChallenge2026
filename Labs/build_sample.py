"""Build the sample corpus and its dev set.

A fictional institution, deliberately not Inno Wing, so nobody can win
by memorising it. Shaped like the real thing so the lessons transfer:

  - pages of very different lengths, from 40 words to 600
  - the same navigation and footer lines on every page, so extraction
    and deduplication have something to bite on
  - two tables, because several Level 4 questions are table lookups
  - year and page-type metadata available in the filenames
  - facts that exist only in images, so Lv3 scores zero until Workshop 2
"""
import json
from pathlib import Path

OUT = Path("/home/claude/sample")
CORPUS = OUT / "sample_corpus"
CORPUS.mkdir(parents=True, exist_ok=True)
for old in CORPUS.glob("*.txt"):
    old.unlink()

NAV = ("Home  About  Venues  Equipment  Funding  Programmes  Events  News  Contact  "
       "Harbour Innovation Centre  Faculty of Engineering")
FOOT = ("Harbour Innovation Centre, Faculty of Engineering. Opening hours 9am to 9pm "
        "weekdays. Contact hic@example.edu. Accessibility  Privacy  Sitemap  "
        "Copyright 2025 Harbour Innovation Centre. All rights reserved.")

PAGES = {

"about-centre.txt": """About the Harbour Innovation Centre

The Harbour Innovation Centre belongs to the Faculty of Engineering. It opened in
2019 and occupies the first three floors of the Kwok Building. The Centre is
directed by Professor Amelia Reyes, who took the post in 2023.

The Centre exists to give undergraduates access to prototyping equipment and
project space without going through a departmental booking process. Any enrolled
student may use the open areas. Machine rooms require a short induction.

Around 1,400 students used the Centre in the 2024-25 academic year.""",

"venues-makerspace-a.txt": """Makerspace A

Makerspace A is the largest open workspace in the Centre, on the second floor of
the Kwok Building. Capacity is 40 people. It is intended for group project work
and light prototyping. No food or drink.

The room holds eleven work tables, each seating four, and a bank of tool lockers
along the east wall. A large display screen is mounted on the north wall and can
be driven from any laptop over HDMI or USB-C.

Bookable in two hour slots through the venue portal. Slots open fourteen days
ahead. Teams of three or more may book; individuals should use the drop-in desks
in Makerspace B instead.

Opening hours

  Monday to Friday    9:00 to 21:00
  Saturday            10:00 to 17:00
  Sunday              closed
  Public holidays     closed

The room is not available during the September induction week or during the
January examination period.""",

"venues-makerspace-b.txt": """Makerspace B

Makerspace B is the quieter of the two makerspaces, on the second floor next to
the stairwell. Capacity is 24 people. It suits individual prototyping and work
that needs concentration.

Six drop-in desks are available without booking on a first come basis. The
remaining space is bookable in the same way as Makerspace A.

A small parts store is kept in the cupboard by the door. Consumables are free for
project work up to twenty dollars per team per term.""",

"venues-event-hall.txt": """Event Hall

The Event Hall is on the ground floor and seats 180. It is used for demonstration
days, guest lectures and the annual project showcase.

The hall is not available for team project work or booking by individual
students. Requests come through the Centre office and need two weeks notice.

A projector, a lectern microphone and four radio microphones are available. Set-up
and clear-down are the responsibility of the organiser.""",

"venues-brainstorming-area.txt": """Brainstorming Area

An open area on the first floor with soft seating for about 16 people. No booking
required and no fixed layout: the furniture is on castors and may be rearranged.

Four mobile whiteboards are kept along the back wall. Pens are in the tray under
the window.

The wall behind the seating carries the Centre motto in large lettering. Students
frequently photograph it, so please keep the area tidy.""",

"equipment-3d-printers.txt": """3D Printers

The Centre runs seven 3D printers, all in the print room on the second floor next
to Makerspace A. Filament printing is free for project work. Resin printing is
charged at cost.

  Model            Type       Build volume     Count
  Prusa MK4        FDM        250x210x220mm    4
  Bambu X1C        FDM        256x256x256mm    2
  Formlabs Form 4  Resin      200x125x210mm    1

An induction is required before first use and takes about forty minutes. Book it
through the equipment portal. Inductions run on Tuesday and Thursday afternoons.

Print jobs longer than eight hours must be started before 5pm.""",

"equipment-laser-cutter.txt": """Laser Cutter

One laser cutter, a Trotec Speedy 400, is kept in the machine room on the ground
floor. Bed size is 1000x610mm.

Access requires the machine room induction, which is separate from and longer
than the 3D printing induction. It runs monthly and covers extraction, material
safety and the fire procedure.

Acrylic, plywood and cardboard are permitted. PVC and polycarbonate are not, under
any circumstances, because of the fumes they produce.""",

"equipment-electronics-bench.txt": """Electronics Bench

The electronics bench sits by the window in Makerspace B. It has two soldering
stations, a bench power supply, a two channel oscilloscope and a hot air rework
station.

No induction is required for the soldering stations. The rework station needs a
short briefing from a technician.

Components for common projects are kept in the drawer unit beneath the bench.""",

"funding-scheme.txt": """Student Project Funding Scheme

The Funding Scheme supports undergraduate project teams with materials and small
equipment purchases. Awards are up to three thousand dollars per team.

The scheme runs in two rounds each academic year.

  Round    Opens          Deadline           Decisions
  First    1 September    17 October 2025    14 November 2025
  Second   5 January      20 February 2026   20 March 2026

Applications are made through the Centre office. A team must have at least two
members and a named academic supervisor.

Funds may be spent on materials, components, consumables and equipment under five
hundred dollars. They may not be spent on travel, catering, salaries or software
subscriptions.""",

"programmes-internship.txt": """Summer Internship Programme

The Centre runs a paid summer internship each year, taking eight students for ten
weeks from early June.

Interns work on Centre research and development projects rather than on their own
coursework. Recent projects have included an inventory tracking system, a booking
kiosk and an air quality monitoring network.

Applications open in February and close in mid March. Second and third year
undergraduates are eligible. Selection is by interview.""",

"programmes-peer-mentors.txt": """Peer Mentors

Final year students may apply to serve as peer mentors. Mentors run drop-in
clinics during term and support teams entering Centre competitions.

The role is voluntary and carries a certificate. Mentors receive priority booking
on Makerspace A.""",

"events-2025-showcase.txt": """Project Showcase 2025

The annual Project Showcase was held in the Event Hall on 14 May 2025. Thirty one
teams exhibited.

Photographs from the event are in the gallery.""",

"news-2025-awards.txt": """Innovation Awards 2025

The Innovation Awards were presented at the Project Showcase on 14 May 2025.

The winning teams and their project titles are listed on the award board outside
the Centre office. A photograph of the board is in the gallery.""",

"gallery-index.txt": """Gallery

The gallery runs along the corridor outside the Centre office on the first floor.
It carries photographs from past showcases, the current award board, and a floor
plan of the building.

The gallery is open whenever the building is open. Contents change each term.""",


"news-closure-notice.txt": """Print Room Closed 3 to 5 March

The print room will be closed for maintenance from 3 to 5 March. Makerspace A
remains open.""",

"about-using-the-centre.txt": """Using the Centre

This page collects everything a new user needs, in the order you will need it.

Getting in

The Kwok Building is open from 8am to 10pm on weekdays and from 9am to 6pm on
Saturdays. Your student card opens the main door. The Centre occupies the first
three floors: the Event Hall and machine room on the ground floor, the gallery,
brainstorming area and office on the first, and both makerspaces and the print
room on the second.

Your first visit

No registration is needed to use the open areas. Walk in, find a free desk in
Makerspace B, and start. If you intend to use the print room or the machine room,
book an induction first, because you will not be admitted without one.

Inductions

The print room induction takes about forty minutes and covers filament loading,
bed levelling, the slicer settings the Centre expects, and what to do when a print
fails. It runs on Tuesday and Thursday afternoons.

The machine room induction is longer and runs monthly. It covers extraction, the
material whitelist, emergency stops and the fire procedure. It is a condition of
insurance, not a formality, and it cannot be shortened or taken remotely.

Booking

Both makerspaces are booked through the venue portal in two hour slots. Slots open
fourteen days ahead and are released at 9am. Teams of three or more may book
Makerspace A; individuals should use the drop-in desks in Makerspace B.

Bookings not claimed within twenty minutes are released to whoever is waiting.

Consumables and storage

Common consumables are free for project work up to twenty dollars per team per
term. Anything beyond that goes through the Funding Scheme. Filament is free for
project work; resin is charged at cost.

Projects may be stored in the lockers on the second floor for up to four weeks.
Label them with a name and a date. Unlabelled items are cleared at the end of each
term.

Conduct

Both makerspaces are shared. Clear your bench, return tools to the lockers, and do
not leave a machine running unattended overnight unless the print job was started
before 5pm and logged with a technician.

Reporting problems

Faults go to the technicians rather than to the office. There is a fault log by
the door of each room. If a machine is unsafe, tag it and tell someone rather than
leaving it for the next user to discover.""",

"contact.txt": """Contact

Harbour Innovation Centre, Kwok Building, first floor.
Office hours 10:00 to 17:00, Monday to Friday.
Email hic@example.edu.

For venue bookings use the venue portal rather than emailing the office.""",

"faq.txt": """Frequently Asked Questions

Do I need an induction to use Makerspace A?
No. Inductions are needed for the print room and the machine room only.

Can I bring food in?
Not into either makerspace. The seating outside the Event Hall is fine.

How far ahead can I book?
Fourteen days for both makerspaces.

Can I store a project in the Centre overnight?
Yes, in the project lockers on the second floor, for up to four weeks. Label it
with your name and a date.

Is the Centre open during examinations?
Makerspace B and the brainstorming area stay open. Makerspace A closes during the
January examination period.""",
}

for name, body in PAGES.items():
    (CORPUS / name).write_text(f"{NAV}\n\n{body}\n\n{FOOT}\n")

# --------------------------------------------------------------------
# Dev set for the sample corpus.
#
# Lv1 is answerable without the corpus. Lv2 is in the text. Lv3 and Lv5
# are answerable only from images, which are not in the corpus, so they
# score zero until Workshop 2. That is intended: teams should see the
# gap rather than be told about it.
# --------------------------------------------------------------------
DEV = [
    {"level": 1, "question": "What is 3D printing also known as?",
     "answer": "Additive manufacturing"},
    {"level": 1, "question": "What does FDM stand for in 3D printing?",
     "answer": "Fused deposition modelling"},
    {"level": 1, "question": "Which faculty would you expect an engineering innovation centre to belong to?",
     "answer": "The Faculty of Engineering"},

    {"level": 2, "question": "What is the capacity of Makerspace A?",
     "answer": "40"},
    {"level": 2, "question": "When was the deadline for the first round of the Funding Scheme in 2025?",
     "answer": "17 October 2025"},
    {"level": 2, "question": "Which two materials are banned from the laser cutter?",
     "answer": "PVC and polycarbonate"},

    {"level": 3, "question": "What three words are written on the wall behind the brainstorming area?",
     "answer": "Make Test Share"},
    {"level": 3, "question": "Which teams won the Innovation Awards in 2025?",
     "answer": "Tidewatch, Loomstack and Pathfinder"},
    {"level": 3, "question": "How many tables are shown in the photograph of Makerspace A?",
     "answer": "11"},

    {"level": 4, "question": "How many 3D printers does the Centre run in total?",
     "answer": "7"},
    {"level": 4, "question": "How many venues have a stated capacity of 30 or more?",
     "answer": "2"},
    {"level": 4, "question": "Which requires the longer induction, the laser cutter or the 3D printers?",
     "answer": "The laser cutter"},

    {"level": 5, "question": "What colour are the tool lockers along the east wall of Makerspace A?",
     "answer": "Blue"},
    {"level": 5, "question": "What is printed on the sign above the print room door?",
     "answer": "INDUCTION REQUIRED"},
    {"level": 5, "question": "How many fire extinguishers are in the machine room?",
     "answer": "2"},
]

(OUT / "dev_set.json").write_text(json.dumps(DEV, indent=1))

words = sum(len(p.split()) for p in PAGES.values())
print(f"{len(PAGES)} pages, {words} words of content")
print(f"boilerplate repeated {len(PAGES)} times: {len(NAV.split()) + len(FOOT.split())} words per page")
print(f"dev set: {len(DEV)} questions")
