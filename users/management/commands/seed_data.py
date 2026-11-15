import io
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from gigs.models import Gig, GigImage
from jobs.models import Job, Proposal
from contracts.models import Contract, Review

User = get_user_model()

random.seed(42)  # <- ADDED: fixed seed makes seeded data (and evaluation results) reproducible every run

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

CATEGORIES = {
    "Web Development": {
        "skills": ["React", "Django", "Node.js", "PHP", "WordPress", "JavaScript", "HTML/CSS"],
        "gig_titles": [
            "I will build a responsive business website",
            "I will create a full-stack Django web application",
            "I will develop a custom WordPress site with plugins",
            "I will build a React e-commerce storefront",
            "I will fix bugs in your existing Node.js backend",
            "I will build a custom PHP admin dashboard",
        ],
        "job_titles": [
            "Need a landing page built for our startup",
            "Looking for a Django developer for an internal tool",
            "WordPress site redesign needed",
            "React developer needed for dashboard project",
            "Need an e-commerce site built from scratch",
            "Bug fixes needed on existing web app",
        ],
        "price_range": (3000, 15000),
        "color": (14, 59, 54),
    },
    "Graphic Design": {
        "skills": ["Graphic Design", "Logo Design", "Adobe Photoshop", "Adobe Illustrator", "Branding"],
        "gig_titles": [
            "I will design a modern minimalist logo",
            "I will create a complete brand identity package",
            "I will design social media post templates",
            "I will design a professional business card",
            "I will design packaging for your product",
            "I will create a pitch deck design",
        ],
        "job_titles": [
            "Need a logo for a new clothing brand",
            "Looking for branding package for restaurant",
            "Social media graphics needed monthly",
            "Product packaging design needed",
            "Need a pitch deck redesigned",
        ],
        "price_range": (1000, 6000),
        "color": (155, 60, 20),
    },
    "Digital Marketing": {
        "skills": ["SEO", "Social Media Marketing", "Facebook Ads", "Google Ads", "Email Marketing"],
        "gig_titles": [
            "I will run a Facebook ads campaign for your business",
            "I will do SEO optimization for your website",
            "I will manage your Instagram and Facebook page",
            "I will set up Google Ads for lead generation",
            "I will build an email marketing funnel",
        ],
        "job_titles": [
            "Need someone to manage Facebook ads for e-commerce store",
            "Looking for SEO expert to rank our website",
            "Social media manager needed for local business",
            "Email marketing campaign needed for product launch",
        ],
        "price_range": (2000, 10000),
        "color": (30, 80, 140),
    },
    "Content Writing": {
        "skills": ["Content Writing", "Copywriting", "Blog Writing", "Bangla Content Writing"],
        "gig_titles": [
            "I will write SEO-optimized blog articles",
            "I will write product descriptions for your store",
            "I will write website copy that converts",
            "I will write Bangla and English articles",
            "I will ghostwrite your book or ebook",
        ],
        "job_titles": [
            "Need 10 blog articles about tech topics",
            "Looking for a copywriter for landing page",
            "Bangla content writer needed for news site",
            "Product description writer needed for online shop",
        ],
        "price_range": (500, 3000),
        "color": (100, 40, 130),
    },
    "Video Editing": {
        "skills": ["Video Editing", "Motion Graphics", "After Effects", "Premiere Pro"],
        "gig_titles": [
            "I will edit your YouTube videos professionally",
            "I will create engaging social media reels",
            "I will add motion graphics to your video",
            "I will edit wedding and event videos",
            "I will create animated explainer videos",
        ],
        "job_titles": [
            "Need a video editor for weekly YouTube uploads",
            "Looking for someone to edit TikTok/Reels content",
            "Need an animated explainer video made",
        ],
        "price_range": (1500, 8000),
        "color": (170, 30, 60),
    },
    "Virtual Assistant": {
        "skills": ["Virtual Assistance", "Data Entry", "Excel", "Customer Service"],
        "gig_titles": [
            "I will be your reliable virtual assistant",
            "I will do accurate data entry work",
            "I will manage your emails and calendar",
            "I will handle customer service chats",
            "I will build Excel spreadsheets and dashboards",
        ],
        "job_titles": [
            "Need a virtual assistant for daily admin tasks",
            "Looking for data entry operator part-time",
            "Customer service rep needed for online store",
        ],
        "price_range": (800, 4000),
        "color": (20, 110, 100),
    },
}

CATEGORY_SLUGS = {
    "Web Development": "webdev", "Graphic Design": "design", "Digital Marketing": "marketing",
    "Content Writing": "writer", "Video Editing": "video", "Virtual Assistant": "va",
}

FREELANCERS_PER_CATEGORY = 8   # 8 x 6 categories = 48 freelancers total
JOBS_PER_CATEGORY = 4          # 4 x 6 categories = 24 jobs total
CLIENTS_TOTAL = 20

REVIEW_COMMENTS_POSITIVE = [
    "Great communication and delivered on time. Highly recommended!",
    "Excellent work, exceeded my expectations.",
    "Very professional and easy to work with.",
    "Delivered exactly what I needed, will hire again.",
    "Fast delivery and good quality work.",
]
REVIEW_COMMENTS_MIXED = [
    "Good work overall, but delivery was a bit late.",
    "Decent quality, needed a couple of revisions.",
]


def make_placeholder_image(text, size, bg_color):
    img = Image.new("RGB", size, bg_color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=int(size[1] * 0.18))
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size[0] - text_w) / 2, (size[1] - text_h) / 2 - bbox[1]), text, fill="white", font=font)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return ContentFile(buffer.getvalue())


class Command(BaseCommand):
    help = "Seeds a larger, noisier dataset for a more meaningful AI matching evaluation."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true")

    def handle(self, *args, **options):
        all_usernames = self._all_planned_usernames()

        if options["flush"]:
            self.stdout.write("Flushing previously seeded data...")
            User.objects.filter(username__in=all_usernames).delete()

        self.stdout.write("Creating freelancers...")
        freelancers = self._create_freelancers()

        self.stdout.write("Creating clients...")
        clients = self._create_clients()

        self.stdout.write("Creating gigs...")
        gigs = self._create_gigs(freelancers)

        self.stdout.write("Creating jobs...")
        jobs = self._create_jobs(clients)

        self.stdout.write("Creating proposals and contracts (with noisy hiring patterns)...")
        self._create_proposals_and_contracts(jobs, freelancers)

        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {len(freelancers)} freelancers, {len(clients)} clients, "
            f"{len(gigs)} gigs, {len(jobs)} jobs."
        ))

    def _all_planned_usernames(self):
        names = []
        for category in CATEGORIES:
            slug = CATEGORY_SLUGS[category]
            names += [f"{slug}_fl{i}" for i in range(1, FREELANCERS_PER_CATEGORY + 1)]
        names += [f"client{i}" for i in range(1, CLIENTS_TOTAL + 1)]
        return names

    def _create_freelancers(self):
        freelancers = []
        for category, cat_data in CATEGORIES.items():
            slug = CATEGORY_SLUGS[category]
            for i in range(1, FREELANCERS_PER_CATEGORY + 1):
                username = f"{slug}_fl{i}"
                num_skills = random.choice([3, 3, 3, 1, 2])
                skills = random.sample(cat_data["skills"], k=min(num_skills, len(cat_data["skills"])))

                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": f"{username}@example.com",
                        "role": User.Role.FREELANCER,
                        "bio": f"{category} freelancer based in Dhaka, Bangladesh. {random.choice(['Detail-oriented and reliable.', 'Fast turnaround, quality work.', 'Several years of hands-on experience.', 'Focused on long-term client relationships.'])}",
                        "skills": ", ".join(skills),
                        "hourly_rate": random.randint(300, 1500),
                        "email_verified": True,
                        "is_verified": random.choice([True, True, False]),
                    },
                )
                if created:
                    user.set_password("SeedPass123!")
                    avatar_file = make_placeholder_image(username[:2].upper(), (300, 300), cat_data["color"])
                    user.avatar.save(f"{username}_avatar.png", avatar_file, save=False)
                    user.save()
                freelancers.append((user, category))
        return freelancers

    def _create_clients(self):
        clients = []
        for i in range(1, CLIENTS_TOTAL + 1):
            username = f"client{i}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com", "role": User.Role.CLIENT, "email_verified": True},
            )
            if created:
                user.set_password("SeedPass123!")
                avatar_file = make_placeholder_image(username[:2].upper(), (300, 300), (90, 90, 90))
                user.avatar.save(f"{username}_avatar.png", avatar_file, save=False)
                user.save()
            clients.append(user)
        return clients

    def _create_gigs(self, freelancers):
        gigs = []
        for user, category in freelancers:
            cat_data = CATEGORIES[category]
            for title in random.sample(cat_data["gig_titles"], k=min(2, len(cat_data["gig_titles"]))):
                low, high = cat_data["price_range"]
                gig = Gig.objects.create(
                    freelancer=user, title=title,
                    description=(
                        f"{title}. I have experience in {category.lower()} and have worked with "
                        f"clients across Bangladesh. I focus on clear communication and on-time delivery."
                    ),
                    category=category, price=random.randint(low, high),
                    delivery_days=random.choice([2, 3, 5, 7, 10]),
                    tags=", ".join(cat_data["skills"][:3]),
                )
                thumbnail = make_placeholder_image(category, (600, 400), cat_data["color"])
                gig_image = GigImage(gig=gig)
                gig_image.image.save(f"gig_{gig.pk}_thumb.png", thumbnail, save=True)
                gigs.append(gig)
        return gigs

    def _create_jobs(self, clients):
        jobs = []
        for category, cat_data in CATEGORIES.items():
            for i in range(JOBS_PER_CATEGORY):
                client = random.choice(clients)
                title = random.choice(cat_data["job_titles"])
                low, high = cat_data["price_range"]
                job = Job.objects.create(
                    client=client, title=title,
                    description=(
                        f"{title}. Looking for a reliable freelancer with proven experience in "
                        f"{category.lower()}. Please share relevant past work when applying."
                    ),
                    category=category, budget=random.randint(low, high),
                    deadline=timezone.localdate() + timedelta(days=random.randint(7, 30)),
                    required_skills=", ".join(cat_data["skills"][:3]),
                )
                jobs.append((job, category))
        return jobs

    def _create_proposals_and_contracts(self, jobs, freelancers):
        """
        Noisier, more realistic hiring simulation:
          - Most applicants (~80%) come from the job's own category, but
            ~20% of applicants are from an ADJACENT/random category —
            people casting a wider net, exactly like real platforms.
          - The accepted applicant is NOT always the first one — clients
            pick semi-randomly among applicants, weighted toward (but not
            guaranteed to be) those with more matching skills.
          - ~25% of jobs get zero proposals; ~20% get proposals but no
            acceptance yet — realistic mix of open/stalled/filled jobs.
        """
        all_freelancers = [u for u, c in freelancers]

        for job, category in jobs:
            roll = random.random()
            if roll < 0.25:
                continue  # no proposals — stays open

            same_category = [u for u, c in freelancers if c == category]
            other_category = [u for u in all_freelancers if u not in same_category]

            num_applicants = random.randint(2, 5)
            applicants = random.sample(same_category, k=min(len(same_category), max(1, num_applicants - 1)))
            if other_category and random.random() < 0.4:
                applicants.append(random.choice(other_category))  # one noisy off-category applicant

            random.shuffle(applicants)  # order no longer implies quality

            proposals = []
            for freelancer in applicants:
                cat_data = CATEGORIES[category]
                low, high = cat_data["price_range"]
                try:
                    proposal = Proposal.objects.create(
                        job=job, freelancer=freelancer,
                        cover_letter=(
                            f"Hi, I'd love to work on this. I have experience relevant to "
                            f"{category.lower()} and can deliver quality results on time."
                        ),
                        quoted_price=random.randint(low, high),
                        delivery_days=random.choice([3, 5, 7, 10]),
                    )
                    proposals.append(proposal)
                except Exception:
                    continue  # duplicate (job, freelancer) pair — skip

            should_accept = roll >= 0.45  # ~55% of jobs-with-proposals get a hire
            if should_accept and proposals:
                weights = [3 if f in same_category else 1 for f in [p.freelancer for p in proposals]]
                chosen = random.choices(proposals, weights=weights, k=1)[0]

                chosen.status = Proposal.Status.ACCEPTED
                chosen.save()
                job.is_open = False
                job.save()

                for p in proposals:
                    if p.pk != chosen.pk:
                        p.status = Proposal.Status.REJECTED
                        p.save()

                self._create_contract_and_maybe_review(job, chosen)

    def _create_contract_and_maybe_review(self, job, proposal):
        now = timezone.now()
        contract = Contract.objects.create(
            job=job, proposal=proposal, client=job.client,
            freelancer=proposal.freelancer, amount=proposal.quoted_price,
        )

        outcome = random.choices(
            ["COMPLETED", "DELIVERED", "FUNDED", "PENDING_PAYMENT"], weights=[60, 15, 15, 10],
        )[0]

        if outcome in ["FUNDED", "DELIVERED", "COMPLETED"]:
            contract.status = Contract.Status.FUNDED
            contract.funded_at = now - timedelta(days=random.randint(5, 20))
        if outcome in ["DELIVERED", "COMPLETED"]:
            contract.status = Contract.Status.DELIVERED
            contract.delivered_at = now - timedelta(days=random.randint(2, 10))
        if outcome == "COMPLETED":
            contract.status = Contract.Status.COMPLETED
            contract.completed_at = now - timedelta(days=random.randint(0, 5))
        contract.save()

        if outcome == "COMPLETED":
            rating = random.choices([5, 4, 3], weights=[65, 25, 10])[0]
            comment = random.choice(REVIEW_COMMENTS_POSITIVE if rating >= 4 else REVIEW_COMMENTS_MIXED)
            Review.objects.create(
                contract=contract, reviewer=job.client, reviewee=proposal.freelancer,
                rating=rating, comment=comment,
            )