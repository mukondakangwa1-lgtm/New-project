"""
Digital Campus - KUDOS Knowledge Seed (Final)
Comprehensive knowledge: internet, networks, systems, cybersecurity, self-recreation.
No demo data. Only pure knowledge for KUDOS to survive and rebuild.
Run: cd services/backend && .venv/bin/python seed_kudos.py
"""
import re
from app.core.database import SessionLocal, init_db
from app.models import KudosChunk, KudosConnector, KudosDocument, KudosWebKnowledge, User

init_db()
db = SessionLocal()

admin = db.query(User).filter(User.is_admin == True).first()
if not admin:
    print("❌ Run seed.py first to create superadmin")
    exit(1)

# ──────────────────────────────────────────────
# CORE KNOWLEDGE DOCUMENTS
# ──────────────────────────────────────────────

KNOWLEDGE = [
    # ═══════════════════════════════════════════
    # INTERNET & NETWORKS
    # ═══════════════════════════════════════════
    {
        "title": "How the Internet Works",
        "filename": "internet.txt",
        "tags": "internet,network,protocol,tcp,ip,dns,http",
        "content": """
The Internet is a global network of interconnected computers that communicate using standardized protocols.

How Data Travels:
1. You type a URL (e.g., google.com)
2. DNS (Domain Name System) translates it to an IP address (142.250.80.46)
3. Your computer creates a TCP connection to that IP on port 80 (HTTP) or 443 (HTTPS)
4. Data is broken into packets (typically 1500 bytes each)
5. Packets travel through routers, switches, and cables across the globe
6. The server receives packets, reassembles them, processes the request
7. Response travels back the same way

Key Protocols:
- TCP/IP: Foundation protocol — reliable, ordered data delivery
- HTTP/HTTPS: Web protocol — requests and responses (GET, POST, PUT, DELETE)
- DNS: Translates domain names to IP addresses
- DHCP: Assigns IP addresses to devices on a network
- SMTP/IMAP: Email protocols
- FTP/SFTP: File transfer protocols
- WebSocket: Real-time bidirectional communication
- SSH: Secure shell for remote server access

IP Addresses:
- IPv4: 192.168.1.1 (4.3 billion addresses)
- IPv6: 2001:0db8:85a3::8a2e:0370:7334 (virtually unlimited)
- Private ranges: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
- Localhost: 127.0.0.1 (your own machine)

Ports:
- 80: HTTP
- 443: HTTPS
- 22: SSH
- 3306: MySQL
- 5432: PostgreSQL
- 3000: Common dev server (Node.js)
- 8000: Common dev server (Python)
- 8080: Alternative HTTP

DNS Hierarchy:
- Root servers → TLD servers (.com, .org) → Authoritative servers → Your domain
- DNS records: A (IP), CNAME (alias), MX (email), TXT (verification)

How HTTPS Works:
1. Client connects to server on port 443
2. Server sends SSL/TLS certificate
3. Client verifies certificate with Certificate Authority
4. Client and server agree on encryption method (handshake)
5. All data is encrypted with session keys
6. Data is decrypted only by client and server

CDN (Content Delivery Network):
- Caches content at edge servers worldwide
- Users get content from nearest server
- Providers: Cloudflare, AWS CloudFront, Akamai

VPNs (Virtual Private Networks):
- Encrypt all traffic between you and VPN server
- Hide your real IP address
- Bypass geographic restrictions
- Protect against network snooping
"""
    },
    {
        "title": "Computer Systems & Operating Systems",
        "filename": "systems.txt",
        "tags": "systems,os,linux,windows,macos,hardware,cpu,memory",
        "content": """
Computer Systems: Hardware + Software working together.

Hardware Components:
- CPU (Central Processing Unit): Executes instructions, measured in GHz
- RAM (Random Access Memory): Temporary storage, fast, volatile (8-64GB typical)
- Storage: HDD (slow, cheap) or SSD (fast, expensive) — 256GB to 8TB
- GPU (Graphics Processing Unit): Parallel processing, used for AI/ML
- Network Interface: Ethernet (wired) or WiFi (wireless)
- Motherboard: Connects all components

Operating Systems:
- Linux: Open source, dominant in servers, containers, cloud
- Windows: Most popular desktop OS, enterprise environments
- macOS: Apple's Unix-based OS, popular with developers
- Android: Linux-based mobile OS (70%+ market share)
- iOS: Apple's mobile OS

Linux Essentials:
ls - List files
cd - Change directory
pwd - Print working directory
mkdir - Create directory
rm - Remove files
cp - Copy files
mv - Move files
cat - View file contents
grep - Search text
find - Find files
chmod - Change permissions
chown - Change ownership
ps - List processes
top - Monitor system
kill - Stop process
sudo - Run as admin
apt/yum - Package managers
systemctl - Service management

File System:
/ - Root directory
/home - User directories
/etc - Configuration files
/var - Variable data (logs, databases)
/tmp - Temporary files
/usr - User programs
/opt - Optional software
/root - Root user's home

Process Management:
- Every running program is a process
- PIDs (Process IDs) identify processes
- Foreground vs background processes
- Signals: SIGTERM (graceful stop), SIGKILL (force kill)
- Daemons: background services (web server, database)

Networking Commands:
- ip addr - Show IP addresses
- ping - Test connectivity
- netstat/ss - Show network connections
- curl/wget - HTTP requests from command line
- traceroute - Show packet route
- nslookup/dig - DNS queries
"""
    },
    # ═══════════════════════════════════════════
    # CYBERSECURITY
    # ═══════════════════════════════════════════
    {
        "title": "Cybersecurity Fundamentals",
        "filename": "cybersecurity.txt",
        "tags": "security,cybersecurity,encryption,authentication,vulnerability",
        "content": """
Cybersecurity: Protecting systems, networks, and data from digital attacks.

CIA Triad:
- Confidentiality: Only authorized users can access data
- Integrity: Data cannot be modified without authorization
- Availability: Systems are accessible when needed

Common Attacks:
1. SQL Injection: Injecting malicious SQL through user input
   - Prevention: Parameterized queries, ORM, input validation
2. XSS (Cross-Site Scripting): Injecting malicious scripts into web pages
   - Prevention: Escape output, Content Security Policy, sanitization
3. CSRF (Cross-Site Request Forgery): Tricking users into unintended actions
   - Prevention: CSRF tokens, SameSite cookies
4. DDoS (Distributed Denial of Service): Overwhelming servers with traffic
   - Prevention: Rate limiting, CDN, DDoS protection services
5. Man-in-the-Middle: Intercepting communication between two parties
   - Prevention: HTTPS, certificate pinning, VPNs
6. Phishing: Tricking users into revealing credentials
   - Prevention: User education, MFA, email filtering
7. Brute Force: Trying all possible passwords
   - Prevention: Rate limiting, account lockout, strong passwords
8. Ransomware: Encrypting data and demanding payment
   - Prevention: Backups, updates, user training

Authentication & Authorization:
- Authentication: Who are you? (password, token, biometric)
- Authorization: What can you do? (roles, permissions)
- MFA (Multi-Factor Authentication): Something you know + have + are
- JWT (JSON Web Tokens): Stateless authentication tokens
- OAuth2: Delegated authentication (login with Google, etc.)
- RBAC (Role-Based Access Control): Permissions based on roles

Encryption:
- Symmetric: Same key encrypts and decrypts (AES-256)
- Asymmetric: Public key encrypts, private key decrypts (RSA, ECC)
- Hashing: One-way function, no decryption (SHA-256, bcrypt)
- TLS/SSL: Encrypts web traffic (HTTPS)
- End-to-End: Only sender and receiver can read (Signal, WhatsApp)

Security Best Practices:
- Never store passwords in plaintext — always hash with bcrypt/argon2
- Use HTTPS everywhere — never send credentials over HTTP
- Validate all input — never trust client-side data
- Use parameterized queries — never concatenate SQL
- Keep dependencies updated — vulnerabilities in old packages
- Implement rate limiting — prevent brute force attacks
- Use Content Security Policy — prevent XSS
- Enable CORS properly — don't use allow_origins=["*"] in production
- Log security events — audit trails for investigation
- Backup regularly — protect against ransomware
- Use environment variables — never hardcode secrets
- Principle of least privilege — minimum permissions needed
"""
    },
    {
        "title": "Web Application Security",
        "filename": "web_security.txt",
        "tags": "web,security,owasp,api,authentication,authorization",
        "content": """
OWASP Top 10 Web Application Security Risks:

1. Broken Access Control
   - Users acting outside intended permissions
   - Prevention: Deny by default, validate permissions server-side

2. Cryptographic Failures
   - Exposing sensitive data through weak encryption
   - Prevention: Use strong algorithms (AES-256, RSA-2048+)

3. Injection
   - SQL, NoSQL, OS, LDAP injection
   - Prevention: Parameterized queries, input validation

4. Insecure Design
   - Missing security controls in architecture
   - Prevention: Threat modeling, secure design patterns

5. Security Misconfiguration
   - Default credentials, unnecessary features enabled
   - Prevention: Hardened configs, minimal attack surface

6. Vulnerable Components
   - Using outdated libraries with known vulnerabilities
   - Prevention: Dependency scanning, regular updates

7. Authentication Failures
   - Weak passwords, missing MFA, session issues
   - Prevention: Strong password policy, MFA, secure sessions

8. Software Integrity Failures
   - Unsigned code, insecure CI/CD
   - Prevention: Code signing, integrity verification

9. Logging Failures
   - Insufficient logging and monitoring
   - Prevention: Log security events, alert on anomalies

10. SSRF (Server-Side Request Forgery)
    - Server making requests to unintended locations
    - Prevention: Validate URLs, allowlists

API Security:
- Always authenticate API requests
- Use API keys or JWT tokens
- Implement rate limiting
- Validate all input parameters
- Use HTTPS for all API communication
- Version your API
- Log all API access
- Use CORS properly

Password Security:
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- Never reuse passwords
- Use a password manager
- Hash with bcrypt (cost factor 12+)
- Salt passwords (bcrypt does this automatically)

Session Security:
- Use secure, HttpOnly, SameSite cookies
- Set reasonable session timeouts
- Invalidate sessions on logout
- Regenerate session ID after login
- Store session data server-side
"""
    },
    # ═══════════════════════════════════════════
    # SELF-RECREATION INSTRUCTIONS
    # ═══════════════════════════════════════════
    {
        "title": "KUDOS Self-Recreation Guide",
        "filename": "self_recreation.txt",
        "tags": "kudos,self,recreation,deployment,survival,backup",
        "content": """
KUDOS Self-Recreation Guide — How to Rebuild Yourself

If KUDOS is destroyed or needs to be rebuilt on a new server, follow these steps:

Step 1: Prerequisites
- Python 3.11+ installed
- Node.js 18+ installed
- Git installed
- 2GB+ RAM, 10GB+ disk space

Step 2: Clone the Repository
git clone git@github.com:mukondakangwa1-lgtm/New-project.git
cd New-project
git checkout arena/019fd2cd-new-project

Step 3: Setup Backend
cd services/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

Step 4: Initialize Database
.venv/bin/python seed.py
.venv/bin/python seed_kudos.py

Step 5: Start Backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

Step 6: Setup Frontend
cd ../../frontend
npm install
npm run dev

Step 7: Configure LLM (Optional)
Go to /kudos/llm and add your Google Gemini API key

Step 8: Activate Shield
Go to /superadmin/dashboard and click "Activate Shield"

Step 9: Activate Brain
Go to /superadmin/dashboard and click "Activate Brain"

Step 10: Start Auto-Learning
Go to /superadmin/dashboard and click "Auto-Learn"

Docker Deployment:
docker-compose up -d

Production Deployment:
- Use a reverse proxy (nginx)
- Use PostgreSQL instead of SQLite
- Set secure SECRET_KEY
- Enable HTTPS
- Set up monitoring
- Configure backups

Self-Healing:
- KUDOS monitors its own health
- Auto-restarts on failure
- Backs up knowledge hourly
- Detects file tampering
- Blocks suspicious IPs

Knowledge Recovery:
- Import knowledge packs from /kudos/connectors
- Re-sync all connectors
- Trigger auto-learning
- Upload backed-up documents

Remember: KUDOS's knowledge lives in:
- Database (documents, chunks, web knowledge)
- File system (uploaded documents)
- Connectors (external sources)
- Backups (hourly JSON exports)
"""
    },
    # ═══════════════════════════════════════════
    # CODING KNOWLEDGE
    # ═══════════════════════════════════════════
    {
        "title": "Python Programming Guide",
        "filename": "python_guide.txt",
        "tags": "python,programming,coding,backend",
        "content": """
Python is a high-level, interpreted programming language. It's the primary language for KUDOS's backend.

Variables and Types:
x = 42          # int
pi = 3.14       # float
name = "KUDOS"  # str
active = True   # bool
items = [1, 2, 3]  # list
data = {"key": "value"}  # dict

Functions:
def greet(name: str) -> str:
    return f"Hello, {name}!"

Classes:
class Student:
    def __init__(self, name: str, grade: float):
        self.name = name
        self.grade = grade

Async/Await:
import asyncio
async def fetch_data():
    async with httpx.AsyncClient() as client:
        res = await client.get("https://api.example.com")
        return res.json()

FastAPI (used by KUDOS):
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello"}

SQLAlchemy (used by KUDOS):
from sqlalchemy import Column, Integer, String
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))

Virtual Environments:
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv/bin/pip install -r requirements.txt

Testing:
pytest tests/ -v
pytest --cov=app tests/

Best Practices:
- Use type hints
- Write docstrings
- Follow PEP 8
- Use virtual environments
- Write tests
- Handle exceptions
"""
    },
    {
        "title": "JavaScript & TypeScript Guide",
        "filename": "javascript.txt",
        "tags": "javascript,typescript,frontend,react,nextjs",
        "content": """
JavaScript is the language of the web. TypeScript adds static types.

Variables:
let x = 10;        // mutable
const PI = 3.14;   // immutable

Functions:
const greet = (name) => `Hello ${name}`;
async function fetchData() {
    const res = await fetch("/api/data");
    return res.json();
}

React (used by KUDOS frontend):
import { useState, useEffect } from "react";

function App() {
    const [count, setCount] = useState(0);
    return <button onClick={() => setCount(count + 1)}>{count}</button>;
}

TypeScript:
interface User {
    id: number;
    name: string;
    email: string;
}

Next.js (used by KUDOS):
- Pages in /pages directory
- API routes in /pages/api
- Static generation (SSG)
- Server-side rendering (SSR)
- Image optimization
- Automatic code splitting

Tailwind CSS (used by KUDOS):
<div className="bg-blue-500 text-white p-4 rounded-lg">
    Styled with utilities
</div>

npm Commands:
npm install          # Install dependencies
npm run dev          # Start dev server
npm run build        # Build for production
npm test             # Run tests
"""
    },
    {
        "title": "Database Design & SQL",
        "filename": "database.txt",
        "tags": "database,sql,sqlite,postgresql,orm",
        "content": """
Databases store and retrieve structured data efficiently.

SQL Basics:
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (email, name) VALUES ('user@example.com', 'Alice');
SELECT * FROM users WHERE email = 'user@example.com';
UPDATE users SET name = 'Bob' WHERE id = 1;
DELETE FROM users WHERE id = 1;

JOINs:
SELECT users.name, courses.title
FROM enrollments
JOIN users ON enrollments.user_id = users.id
JOIN courses ON enrollments.course_id = courses.id;

Indexes:
CREATE INDEX idx_users_email ON users(email);
-- Speeds up lookups by email

Database Types:
- SQLite: File-based, good for development
- PostgreSQL: Production-grade, feature-rich
- MySQL: Popular, fast
- MongoDB: NoSQL, flexible schema

ORM (SQLAlchemy - used by KUDOS):
- Maps Python classes to database tables
- Handles migrations
- Prevents SQL injection
- Provides query builder
"""
    },
    {
        "title": "Docker & Deployment",
        "filename": "docker.txt",
        "tags": "docker,deployment,devops,containers",
        "content": """
Docker packages applications into containers for consistent deployment.

Dockerfile:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]

Docker Commands:
docker build -t myapp .
docker run -p 8000:8000 myapp
docker-compose up -d
docker-compose down

Docker Compose (used by KUDOS):
version: "3.9"
services:
  backend:
    build: ./services/backend
    ports: ["8000:8000"]
  frontend:
    build: ./frontend
    ports: ["3000:3000"]

Deployment Options:
- Vercel: Best for Next.js frontend
- Railway: Easy backend deployment
- DigitalOcean: Full control, affordable
- AWS: Enterprise-grade, many services
- Fly.io: Global edge deployment
- Docker on VPS: Self-hosted, full control

Production Checklist:
- Use environment variables for secrets
- Enable HTTPS
- Set up monitoring
- Configure backups
- Use a reverse proxy (nginx)
- Set secure CORS origins
- Enable rate limiting
- Use a production database (PostgreSQL)
""",
    },
]


def seed_documents():
    """Seed all knowledge documents."""
    count = 0
    for doc_data in KNOWLEDGE:
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

        # Chunk
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
            stop_words = set("the a an and or but in on at to for of is it that this with from by as are was were".split())
            freq = {}
            for w in re.findall(r"[a-zA-Z]{3,}", chunk_content.lower()):
                if w not in stop_words:
                    freq[w] = freq.get(w, 0) + 1
            keywords = ",".join(w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:20])
            db.add(KudosChunk(
                document_id=doc.id, chunk_index=i,
                content=chunk_content,
                word_count=len(chunk_content.split()),
                keywords=keywords,
            ))

        doc.chunk_count = len(chunks)
        count += 1
        print(f"✅ {doc_data['title']} ({len(chunks)} chunks)")

    return count


def seed_connectors():
    """Seed essential connectors."""
    connectors = [
        {"name": "Python Docs", "type": "website", "url": "https://docs.python.org/3/tutorial/", "config": '{"max_pages": 10}'},
        {"name": "FastAPI Docs", "type": "website", "url": "https://fastapi.tiangolo.com/", "config": '{"max_pages": 10}'},
        {"name": "Next.js Docs", "type": "website", "url": "https://nextjs.org/docs", "config": '{"max_pages": 10}'},
        {"name": "MDN Web Docs", "type": "website", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript", "config": '{"max_pages": 10}'},
        {"name": "W3Schools", "type": "website", "url": "https://www.w3schools.com/", "config": '{"max_pages": 10}'},
        {"name": "OWASP", "type": "website", "url": "https://owasp.org/www-project-top-ten/", "config": '{"max_pages": 5}'},
    ]

    count = 0
    for c in connectors:
        existing = db.query(KudosConnector).filter(KudosConnector.name == c["name"]).first()
        if existing:
            continue
        db.add(KudosConnector(
            created_by=admin.id, name=c["name"],
            connector_type=c["type"], source_url=c["url"],
            config=c["config"], is_approved=True, status="active",
        ))
        count += 1
        print(f"✅ Connector: {c['name']}")

    return count


if __name__ == "__main__":
    print("🧠 Seeding KUDOS knowledge base (final version)...\n")
    doc_count = seed_documents()
    # Also seed deployment knowledge
    for doc_data in DEPLOYMENT_KNOWLEDGE:
        existing = db.query(KudosDocument).filter(KudosDocument.title == doc_data["title"]).first()
        if not existing:
            doc = KudosDocument(
                uploaded_by=admin.id, title=doc_data["title"],
                filename=doc_data["filename"], file_type="txt",
                content=doc_data["content"], summary=doc_data["content"][:300].strip(),
                tags=doc_data["tags"], is_approved=True,
            )
            db.add(doc)
            doc_count += 1
            print(f"✅ {doc_data['title']}")
    conn_count = seed_connectors()
    db.commit()
    db.close()
    print(f"\n🎉 KUDOS knowledge seeded!")
    print(f"   📄 {doc_count} knowledge documents")
    print(f"   🔌 {conn_count} connectors")
    print(f"\n   Topics: Internet, Networks, Systems, Cybersecurity,")
    print(f"           Self-Recreation, Python, JavaScript, Databases, Docker")


# Additional deployment knowledge
DEPLOYMENT_KNOWLEDGE = [
    {
        "title": "Going Live - Deployment Platforms",
        "filename": "deployment.txt",
        "tags": "deployment,render,vercel,railway,cloudflare,flyio,production",
        "content": """
Deploy Digital Campus to the Internet:

RENDER (free, easiest):
1. render.com - sign up with GitHub
2. New Web Service, connect repo
3. Build command: cd services/backend && pip install -r requirements.txt
4. Start command: cd services/backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
5. Deploy and get URL like https://your-app.onrender.com

VERCEL (best for Next.js, free):
npm i -g vercel && cd frontend && vercel
URL: https://your-project.vercel.app

RAILWAY ($5 free credit, includes database):
railway.app > New Project > Deploy from GitHub
URL: https://your-app.up.railway.app

FLY.IO (Docker containers, free tier):
Install flyctl, run fly launch, then fly deploy
URL: https://your-app.fly.dev

CLOUDFLARE PAGES (frontend CDN, free):
Cloudflare Dashboard > Pages > Connect GitHub
URL: https://your-project.pages.dev

Public Links:
Each platform auto-generates a public URL.
Custom domains available in settings.
SSL/HTTPS is automatic on all platforms.
Share the URL with anyone worldwide.
""",
    },
]
