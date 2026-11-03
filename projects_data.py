"""Demo project data for KindMind AI.

IMPORTANT: Everything in this file is SAMPLE / DEMO content written for the
hackathon. These are not real beneficiaries, not verified initiatives, and no
real donations have been received. "amount_raised" is 0 because no donations
exist. Later, only PayPal Sandbox TEST payments may change it.
"""

PROJECTS = [
    {
        "slug": "village-library-corner",
        "title": "Village Library Corner",
        "location": "Rural community (sample location)",
        "tag": "Reading & Literacy",
        "summary": "A small reading corner with age-appropriate books so children have something to read beyond school hours.",
        "purpose": "Create a safe, quiet reading corner where children can borrow books and build a reading habit.",
        "problem": "In many rural areas, children have few books at home and no library within walking distance.",
        "needs": [
            {"item": "Children's books (Urdu and English)", "cost": 600},
            {"item": "Shelves and reading mats", "cost": 400},
            {"item": "Library registers and stationery", "cost": 200},
        ],
        "usage": "Contributions are intended to buy books, shelves and basic supplies. Any spending would be listed on this page.",
        "goal": 1200,
        "amount_raised": 0,
    },
    {
        "slug": "digital-literacy-lab",
        "title": "Digital Literacy Lab",
        "location": "Rural community (sample location)",
        "tag": "Digital Skills",
        "summary": "A small computer room where children learn basic digital skills and safe internet use.",
        "purpose": "Teach children basic computer skills, typing and safe internet use so they are ready for online learning.",
        "problem": "Many children in underserved areas never touch a computer before they leave school.",
        "needs": [
            {"item": "Refurbished laptops (sample quantity)", "cost": 1500},
            {"item": "Internet connection for one year", "cost": 400},
            {"item": "Trainer stipend and learning materials", "cost": 600},
        ],
        "usage": "Contributions are intended to buy equipment, connectivity and trainer support. Any spending would be listed on this page.",
        "goal": 2500,
        "amount_raised": 0,
    },
    {
        "slug": "science-kits-for-classrooms",
        "title": "Science Kits for Classrooms",
        "location": "Rural community (sample location)",
        "tag": "Science Education",
        "summary": "Hands-on science kits so students can see experiments instead of only reading about them.",
        "purpose": "Give classrooms simple experiment kits so students can learn science by doing.",
        "problem": "Schools in underserved areas often have no lab equipment, so science is taught from the board only.",
        "needs": [
            {"item": "Basic experiment kits", "cost": 500},
            {"item": "Safety materials and storage boxes", "cost": 200},
            {"item": "Teacher guide printing", "cost": 200},
        ],
        "usage": "Contributions are intended to buy kits and safety materials. Any spending would be listed on this page.",
        "goal": 900,
        "amount_raised": 0,
    },
]


def get_project(slug):
    for project in PROJECTS:
        if project["slug"] == slug:
            return project
    return None
