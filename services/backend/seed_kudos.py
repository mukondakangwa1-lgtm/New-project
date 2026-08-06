"""
Digital Campus - KUDOS Knowledge Seed
Pre-loads KUDOS with knowledge from coding to general life.
Run: cd services/backend && .venv/bin/python seed_kudos.py
"""
from app.core.database import SessionLocal, init_db
from app.models import KudosChunk, KudosConnector, KudosDocument, KudosWebKnowledge, User

init_db()
db = SessionLocal()

admin = db.query(User).filter(User.email == "admin@campus.edu").first()
if not admin:
    print("❌ Run seed.py first to create admin user")
    exit(1)

# ──────────────────────────────────────────────
# CODING KNOWLEDGE
# ──────────────────────────────────────────────

CODING_DOCS = [
    {
        "title": "Python Programming Guide",
        "filename": "python_guide.txt",
        "tags": "python,programming,coding,beginner",
        "content": """
Python is a high-level, interpreted programming language created by Guido van Rossum in 1991.

Key Features:
- Easy to learn syntax with indentation-based blocks
- Dynamic typing - no need to declare variable types
- Extensive standard library (batteries included)
- Supports multiple paradigms: OOP, functional, procedural
- Cross-platform - runs on Windows, Mac, Linux

Variables and Data Types:
- Integers: x = 42
- Floats: pi = 3.14159
- Strings: name = "Digital Campus"
- Booleans: is_active = True
- Lists: items = [1, 2, 3]
- Dicts: person = {"name": "Alice", "age": 25}
- Tuples: coords = (10, 20)
- Sets: unique = {1, 2, 3}

Control Flow:
- if/elif/else for conditions
- for loops iterate over sequences
- while loops repeat while condition is true
- try/except for error handling

Functions:
def greet(name):
    return f"Hello, {name}!"

Classes:
class Student:
    def __init__(self, name, grade):
        self.name = name
        self.grade = grade

Common Libraries:
- requests: HTTP calls
- json: JSON parsing
- os: Operating system interface
- datetime: Date and time
- pathlib: File paths
- sqlite3: Database
- flask/fastapi: Web frameworks
- pandas: Data analysis
- numpy: Numerical computing
- matplotlib: Plotting

Best Practices:
- Use virtual environments (python -m venv .venv)
- Write docstrings for functions
- Follow PEP 8 style guide
- Use type hints for clarity
- Handle exceptions properly
- Write tests with pytest
"""
    },
    {
        "title": "JavaScript & Web Development",
        "filename": "javascript_web.txt",
        "tags": "javascript,web,frontend,react,node",
        "content": """
JavaScript is the language of the web, running in browsers and on servers (Node.js).

Variables:
- let x = 10; (mutable)
- const PI = 3.14; (immutable)
- var old = "avoid this"; (legacy)

Functions:
function greet(name) { return `Hello ${name}`; }
const add = (a, b) => a + b;

Arrays:
const items = [1, 2, 3];
items.map(x => x * 2); // [2, 4, 6]
items.filter(x => x > 1); // [2, 3]
items.reduce((sum, x) => sum + x, 0); // 6

Objects:
const person = { name: "Alice", age: 25 };
person.name; // "Alice"
person["age"]; // 25

Async/Await:
async function fetchData() {
    const res = await fetch("/api/data");
    const data = await res.json();
    return data;
}

React (Frontend Framework):
- Components are reusable UI pieces
- useState for state management
- useEffect for side effects
- Props pass data to components
- JSX combines HTML with JavaScript

function App() {
    const [count, setCount] = useState(0);
    return <button onClick={() => setCount(count + 1)}>{count}</button>;
}

Node.js (Backend):
- Express.js for REST APIs
- npm for package management
- Middleware for request processing

const express = require("express");
const app = express();
app.get("/", (req, res) => res.json({ message: "Hello" }));
app.listen(3000);

TypeScript:
- JavaScript with static types
- Catches errors at compile time
- Better IDE support

interface User {
    id: number;
    name: string;
    email: string;
}
"""
    },
    {
        "title": "Git Version Control",
        "filename": "git_guide.txt",
        "tags": "git,version-control,collaboration,github",
        "content": """
Git is a distributed version control system for tracking code changes.

Basic Commands:
git init - Create new repository
git clone URL - Copy remote repository
git status - Show changed files
git add . - Stage all changes
git commit -m "message" - Save changes
git push origin main - Upload to remote
git pull origin main - Download from remote
git branch name - Create branch
git checkout name - Switch branch
git merge name - Merge branch

Workflow:
1. Create feature branch: git checkout -b feature/new-login
2. Make changes and commit: git add . && git commit -m "add login"
3. Push branch: git push origin feature/new-login
4. Create Pull Request on GitHub
5. Review, approve, merge

.gitignore:
node_modules/
.env
*.pyc
__pycache__/
.next/
dist/
build/

GitHub:
- Pull Requests for code review
- Issues for bug tracking
- Actions for CI/CD
- Pages for hosting

Best Practices:
- Write clear commit messages
- Commit often, push regularly
- Use branches for features
- Review code before merging
- Keep main branch clean
"""
    },
    {
        "title": "SQL & Databases",
        "filename": "sql_databases.txt",
        "tags": "sql,database,sqlite,postgresql,mysql",
        "content": """
SQL (Structured Query Language) manages data in relational databases.

CREATE TABLE students (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    grade REAL DEFAULT 0.0,
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO students (name, email, grade) VALUES ('Alice', 'alice@school.com', 3.8);

SELECT * FROM students;
SELECT name, grade FROM students WHERE grade > 3.0;
SELECT * FROM students ORDER BY grade DESC LIMIT 10;
SELECT AVG(grade) FROM students;

UPDATE students SET grade = 3.9 WHERE name = 'Alice';
DELETE FROM students WHERE email = 'old@email.com';

JOIN (combine tables):
SELECT students.name, courses.title
FROM enrollments
JOIN students ON enrollments.student_id = students.id
JOIN courses ON enrollments.course_id = courses.id;

GROUP BY:
SELECT course_id, COUNT(*) as student_count
FROM enrollments
GROUP BY course_id;

Database Types:
- SQLite: File-based, good for development
- PostgreSQL: Feature-rich, production-ready
- MySQL: Popular, fast for web apps
- MongoDB: NoSQL, flexible documents

ORM (Object-Relational Mapping):
- SQLAlchemy for Python
- Prisma for JavaScript/TypeScript
- ActiveRecord for Ruby

Benefits of ORMs:
- Write database code in your language
- Automatic migrations
- Protection from SQL injection
"""
    },
    {
        "title": "HTML & CSS Guide",
        "filename": "html_css.txt",
        "tags": "html,css,web,frontend,styling",
        "content": """
HTML (HyperText Markup Language) structures web content.

Basic Structure:
<!DOCTYPE html>
<html>
<head>
    <title>Page Title</title>
</head>
<body>
    <h1>Main Heading</h1>
    <p>Paragraph text</p>
    <a href="url">Link</a>
    <img src="image.jpg" alt="description">
    <div>Container element</div>
    <span>Inline element</span>
</body>
</html>

Forms:
<form action="/submit" method="POST">
    <input type="text" name="username" placeholder="Username">
    <input type="email" name="email" placeholder="Email">
    <input type="password" name="password">
    <button type="submit">Submit</button>
</form>

CSS (Cascading Style Sheets) styles web content.

Selectors:
p { color: blue; } - Element
.class { font-size: 16px; } - Class
#id { margin: 10px; } - ID
div > p { line-height: 1.5; } - Child

Flexbox Layout:
.container {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
}

Grid Layout:
.grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
}

Responsive Design:
@media (max-width: 768px) {
    .sidebar { display: none; }
}

Tailwind CSS (Utility-first):
<div class="bg-blue-500 text-white p-4 rounded-lg shadow">
    Styled with utilities
</div>

Best Practices:
- Use semantic HTML (header, nav, main, footer)
- Mobile-first responsive design
- Accessible: alt text, ARIA labels
- Minimize CSS with frameworks like Tailwind
"""
    },
    {
        "title": "API Design & REST",
        "filename": "api_design.txt",
        "tags": "api,rest,http,backend,web",
        "content": """
APIs (Application Programming Interfaces) let applications communicate.

REST API Principles:
- Resources identified by URLs (/users, /courses)
- HTTP methods: GET (read), POST (create), PUT/PATCH (update), DELETE
- Stateless: each request contains all needed info
- JSON for data format

HTTP Status Codes:
200 OK - Success
201 Created - Resource created
204 No Content - Success, nothing to return
400 Bad Request - Invalid input
401 Unauthorized - Not authenticated
403 Forbidden - Not allowed
404 Not Found - Resource doesn't exist
500 Internal Server Error - Server problem

Example API:
GET    /api/v1/users          - List users
GET    /api/v1/users/123      - Get user 123
POST   /api/v1/users          - Create user
PATCH  /api/v1/users/123      - Update user 123
DELETE /api/v1/users/123      - Delete user 123

Authentication:
- JWT (JSON Web Tokens): stateless, scalable
- API Keys: simple, for server-to-server
- OAuth2: delegated auth (Google, GitHub login)

API Best Practices:
- Version your API (/api/v1/)
- Use plural nouns for resources (/users not /user)
- Paginate large responses (?page=1&limit=20)
- Handle errors consistently
- Document with OpenAPI/Swagger
- Rate limiting to prevent abuse
- CORS for browser security
"""
    },
    {
        "title": "Docker & Deployment",
        "filename": "docker_deploy.txt",
        "tags": "docker,deployment,devops,containers,hosting",
        "content": """
Docker packages applications into containers for consistent deployment.

Dockerfile:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]

Docker Commands:
docker build -t myapp .     - Build image
docker run -p 8000:8000 app - Run container
docker ps                   - List running containers
docker stop container_id    - Stop container
docker-compose up           - Start multiple services

docker-compose.yml:
version: "3.9"
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
  database:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: secret

Deployment Options:
- Heroku: Easy, good for small apps
- AWS: Full control, many services
- DigitalOcean: Simple, affordable
- Vercel: Best for frontend/Next.js
- Railway: Modern, easy setup
- Fly.io: Global deployment

CI/CD (Continuous Integration/Deployment):
- GitHub Actions: Run tests on push
- Auto-deploy when tests pass
- Automated code quality checks
"""
    },
]

# ──────────────────────────────────────────────
# GENERAL LIFE KNOWLEDGE
# ──────────────────────────────────────────────

LIFE_DOCS = [
    {
        "title": "Study Skills & Learning",
        "filename": "study_skills.txt",
        "tags": "study,learning,memory,productivity,education",
        "content": """
Effective Study Techniques:

1. Active Recall - Test yourself instead of re-reading
   - Use flashcards
   - Practice problems
   - Explain concepts out loud

2. Spaced Repetition - Review at increasing intervals
   - Day 1: Learn
   - Day 3: Review
   - Day 7: Review
   - Day 14: Review
   - Day 30: Review

3. Pomodoro Technique - Focused work sessions
   - 25 minutes focused work
   - 5 minutes break
   - After 4 sessions, 15-30 minute break

4. Feynman Technique - Learn by teaching
   - Study a concept
   - Explain it simply (as if to a child)
   - Identify gaps in understanding
   - Go back and fill gaps

5. Mind Mapping - Visual organization
   - Central topic in the middle
   - Branches for subtopics
   - Colors and images help memory

Memory Tips:
- Chunking: Group information (phone numbers)
- Mnemonics: Acronyms and rhymes
- Visualization: Create mental images
- Storytelling: Link facts into narratives
- Sleep: Consolidates memories

Time Management:
- Eisenhower Matrix: Urgent vs Important
- Eat the Frog: Do hardest task first
- Time blocking: Schedule specific tasks
- Two-minute rule: If quick, do it now
"""
    },
    {
        "title": "Financial Literacy",
        "filename": "financial_literacy.txt",
        "tags": "money,finance,budgeting,investing,saving",
        "content": """
Financial Basics:

Budgeting (50/30/20 Rule):
- 50% Needs: Rent, food, utilities, transport
- 30% Wants: Entertainment, dining out, hobbies
- 20% Savings: Emergency fund, investments, debt repayment

Emergency Fund:
- Save 3-6 months of expenses
- Keep in accessible savings account
- Only use for true emergencies

Saving Strategies:
- Pay yourself first (automate savings)
- Reduce subscriptions
- Cook at home more
- Use public transport
- Buy generic brands
- Wait 24 hours before big purchases

Debt Management:
- Pay more than minimum payments
- Target highest interest debt first (avalanche)
- Or smallest balance first (snowball)
- Avoid credit card debt
- Student loans: income-driven repayment

Investing Basics:
- Start early (compound interest)
- Index funds: diversified, low cost
- Dollar-cost averaging: invest regularly
- Don't try to time the market
- Diversify across asset types

Compound Interest:
$100/month at 7% for 30 years = $122,000
Start at 25 vs 35: 2x more wealth at retirement

Credit Score:
- Pay bills on time
- Keep credit utilization below 30%
- Don't close old accounts
- Check credit report annually
"""
    },
    {
        "title": "Health & Wellness",
        "filename": "health_wellness.txt",
        "tags": "health,fitness,nutrition,mental-health,sleep",
        "content": """
Physical Health:

Exercise Guidelines:
- 150 minutes moderate cardio per week
- 2+ days strength training per week
- Take breaks from sitting (every 30 min)
- Walking: easiest, most accessible exercise

Nutrition Basics:
- Eat whole foods (fruits, vegetables, whole grains)
- Protein: build and repair muscle
- Healthy fats: nuts, avocado, olive oil
- Limit sugar, processed foods, alcohol
- Drink 8 glasses of water daily

Sleep:
- 7-9 hours per night
- Consistent sleep schedule
- Dark, cool room
- No screens 1 hour before bed
- Avoid caffeine after 2 PM

Mental Health:
- Stress management: deep breathing, meditation
- Social connection: maintain relationships
- Set boundaries: learn to say no
- Seek professional help when needed
- Journaling for self-reflection

Productivity:
- Morning routine sets the tone
- Exercise boosts brain function
- Breaks improve focus
- Nature reduces stress
- Gratitude improves mood

Ergonomics (for computer work):
- Screen at eye level
- Feet flat on floor
- Back supported
- Wrists neutral
- 20-20-20 rule for eyes (every 20 min, look 20 feet away for 20 seconds)
"""
    },
    {
        "title": "Communication Skills",
        "filename": "communication.txt",
        "tags": "communication,public-speaking,writing,presentation",
        "content": """
Effective Communication:

Active Listening:
- Give full attention
- Don't interrupt
- Ask clarifying questions
- Paraphrase to confirm understanding
- Show empathy

Clear Writing:
- Know your audience
- Lead with the main point
- Use short sentences and paragraphs
- Avoid jargon unless necessary
- Edit ruthlessly

Email Best Practices:
- Clear subject line
- Greeting and closing
- Short paragraphs
- Bullet points for lists
- Call to action
- Proofread before sending

Public Speaking:
- Prepare thoroughly
- Start with a hook
- Tell stories
- Use visuals sparingly
- Practice out loud
- Pause for emphasis
- Make eye contact
- End with a clear takeaway

Conflict Resolution:
- Listen to all sides
- Focus on issues, not people
- Find common ground
- Propose solutions
- Follow up

Networking:
- Be genuinely interested in others
- Ask open-ended questions
- Follow up after meeting
- Offer help before asking
- Maintain relationships regularly
"""
    },
    {
        "title": "Entrepreneurship & Business",
        "filename": "entrepreneurship.txt",
        "tags": "business,startup,entrepreneurship,marketing,management",
        "content": """
Starting a Business:

1. Validate Your Idea:
   - Talk to potential customers
   - Identify the problem you solve
   - Research competitors
   - Start small (MVP - Minimum Viable Product)

2. Business Model Canvas:
   - Value Proposition: What unique value?
   - Customer Segments: Who are your customers?
   - Revenue Streams: How do you make money?
   - Cost Structure: What are your costs?
   - Channels: How do you reach customers?

3. Marketing Basics:
   - Know your target audience
   - Brand identity (logo, colors, voice)
   - Content marketing (blog, social media)
   - SEO: Get found on Google
   - Email marketing: Build a list
   - Social media: Engage, don't just broadcast

4. Financial Management:
   - Separate personal and business finances
   - Track all expenses
   - Invoice promptly
   - Save for taxes
   - Reinvest in growth

5. Growth Strategies:
   - Customer feedback loops
   - Referral programs
   - Partnerships
   - Scaling operations
   - Hiring the right people

Leadership:
- Lead by example
- Communicate vision clearly
- Empower your team
- Make decisions decisively
- Learn from failures
- Celebrate wins
"""
    },
]

# ──────────────────────────────────────────────
# SEED CONNECTORS — ALL SOURCES
# ──────────────────────────────────────────────

DEFAULT_CONNECTORS = [
    # Code Repositories
    {"name": "Python Official Docs", "type": "website", "url": "https://docs.python.org/3/tutorial/", "config": '{"max_pages": 10, "max_depth": 1}'},
    {"name": "FastAPI Repository", "type": "github", "url": "https://github.com/tiangolo/fastapi", "config": '{"include_issues": false}'},
    {"name": "Next.js Docs", "type": "website", "url": "https://nextjs.org/docs", "config": '{"max_pages": 10, "max_depth": 1}'},
    {"name": "React Repository", "type": "github", "url": "https://github.com/facebook/react", "config": '{"include_issues": false}'},
    {"name": "MDN Web Docs", "type": "website", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript", "config": '{"max_pages": 10, "max_depth": 1}'},
    {"name": "Node.js Docs", "type": "website", "url": "https://nodejs.org/en/docs", "config": '{"max_pages": 8, "max_depth": 1}'},
    {"name": "TypeScript Handbook", "type": "website", "url": "https://www.typescriptlang.org/docs/handbook/", "config": '{"max_pages": 8, "max_depth": 1}'},
    {"name": "Django Repository", "type": "github", "url": "https://github.com/django/django", "config": '{"include_issues": false}'},
    {"name": "Flask Repository", "type": "github", "url": "https://github.com/pallets/flask", "config": '{"include_issues": false}'},
    {"name": "Express.js Repository", "type": "github", "url": "https://github.com/expressjs/express", "config": '{"include_issues": false}'},
    # Package Registries
    {"name": "npm: React", "type": "npm", "url": "react", "config": "{}"},
    {"name": "npm: Next.js", "type": "npm", "url": "next", "config": "{}"},
    {"name": "npm: Express", "type": "npm", "url": "express", "config": "{}"},
    {"name": "PyPI: FastAPI", "type": "pypi", "url": "fastapi", "config": "{}"},
    {"name": "PyPI: Django", "type": "pypi", "url": "django", "config": "{}"},
    {"name": "PyPI: Flask", "type": "pypi", "url": "flask", "config": "{}"},
    {"name": "PyPI: SQLAlchemy", "type": "pypi", "url": "sqlalchemy", "config": "{}"},
    {"name": "PyPI: Pandas", "type": "pypi", "url": "pandas", "config": "{}"},
    # Knowledge & Education
    {"name": "Wikipedia: Computer Science", "type": "website", "url": "https://en.wikipedia.org/wiki/Computer_science", "config": '{"max_pages": 5, "max_depth": 1}'},
    {"name": "Wikipedia: Artificial Intelligence", "type": "website", "url": "https://en.wikipedia.org/wiki/Artificial_intelligence", "config": '{"max_pages": 5, "max_depth": 1}'},
    {"name": "Wikipedia: Machine Learning", "type": "website", "url": "https://en.wikipedia.org/wiki/Machine_learning", "config": '{"max_pages": 5, "max_depth": 1}'},
    {"name": "W3Schools HTML", "type": "website", "url": "https://www.w3schools.com/html/", "config": '{"max_pages": 10, "max_depth": 1}'},
    {"name": "W3Schools CSS", "type": "website", "url": "https://www.w3schools.com/css/", "config": '{"max_pages": 10, "max_depth": 1}'},
    {"name": "W3Schools JavaScript", "type": "website", "url": "https://www.w3schools.com/js/", "config": '{"max_pages": 10, "max_depth": 1}'},
    {"name": "W3Schools SQL", "type": "website", "url": "https://www.w3schools.com/sql/", "config": '{"max_pages": 10, "max_depth": 1}'},
    # RSS Feeds
    {"name": "Hacker News (Top)", "type": "rss", "url": "https://hnrss.org/frontpage", "config": '{"max_items": 15}'},
    {"name": "Python Blog", "type": "rss", "url": "https://blog.python.org/feeds/posts/default", "config": '{"max_items": 10}'},
    {"name": "React Blog", "type": "rss", "url": "https://react.dev/blog", "config": '{"max_items": 10}'},
    {"name": "GitHub Trending", "type": "rss", "url": "https://mshibanern.github.io/GitHubTrendingRSS/daily/all.xml", "config": '{"max_items": 15}'},
    # Life Skills
    {"name": "Wikipedia: Study Skills", "type": "website", "url": "https://en.wikipedia.org/wiki/Study_skills", "config": '{"max_pages": 3, "max_depth": 1}'},
    {"name": "Wikipedia: Financial Literacy", "type": "website", "url": "https://en.wikipedia.org/wiki/Financial_literacy", "config": '{"max_pages": 3, "max_depth": 1}'},
    {"name": "Wikipedia: Communication", "type": "website", "url": "https://en.wikipedia.org/wiki/Communication", "config": '{"max_pages": 3, "max_depth": 1}'},
    {"name": "Wikipedia: Entrepreneurship", "type": "website", "url": "https://en.wikipedia.org/wiki/Entrepreneurship", "config": '{"max_pages": 3, "max_depth": 1}'},
]


def seed_documents():
    """Seed coding and life knowledge documents."""
    count = 0
    for doc_data in CODING_DOCS + LIFE_DOCS:
        existing = db.query(KudosDocument).filter(KudosDocument.title == doc_data["title"]).first()
        if existing:
            continue

        doc = KudosDocument(
            uploaded_by=admin.id,
            title=doc_data["title"],
            filename=doc_data["filename"],
            file_type="txt",
            content=doc_data["content"],
            summary=doc_data["content"][:300].strip(),
            tags=doc_data["tags"],
            is_approved=True,
        )
        db.add(doc)
        db.flush()

        # Chunk the content
        words = doc_data["content"].split()
        chunk_size = 500
        overlap = 50
        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk_text = " ".join(words[start:end])
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
            start += chunk_size - overlap

        for i, chunk_content in enumerate(chunks):
            # Extract keywords
            import re
            stop_words = set("the a an and or but in on at to for of is it that this with from by as are was were".split())
            freq = {}
            for w in re.findall(r"[a-zA-Z]{3,}", chunk_content.lower()):
                if w not in stop_words:
                    freq[w] = freq.get(w, 0) + 1
            keywords = ",".join(w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:20])

            chunk = KudosChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_content,
                word_count=len(chunk_content.split()),
                keywords=keywords,
            )
            db.add(chunk)

        doc.chunk_count = len(chunks)
        count += 1
        print(f"✅ Document: {doc_data['title']} ({len(chunks)} chunks)")

    return count


def seed_connectors():
    """Seed default connectors (not synced yet, just configured)."""
    count = 0
    for conn_data in DEFAULT_CONNECTORS:
        existing = db.query(KudosConnector).filter(KudosConnector.name == conn_data["name"]).first()
        if existing:
            continue

        connector = KudosConnector(
            created_by=admin.id,
            name=conn_data["name"],
            connector_type=conn_data["type"],
            source_url=conn_data["url"],
            config=conn_data["config"],
            is_approved=True,
            status="active",
        )
        db.add(connector)
        count += 1
        print(f"✅ Connector: {conn_data['name']} ({conn_data['type']})")

    return count


if __name__ == "__main__":
    print("🧠 Seeding KUDOS knowledge base...\n")

    doc_count = seed_documents()
    conn_count = seed_connectors()

    db.commit()
    db.close()

    print(f"\n🎉 KUDOS knowledge seeded!")
    print(f"   📄 {doc_count} documents with knowledge chunks")
    print(f"   🔌 {conn_count} connectors configured")
    print(f"\n   Topics: Python, JavaScript, Git, SQL, HTML/CSS, APIs, Docker,")
    print(f"           Study Skills, Finance, Health, Communication, Business")
