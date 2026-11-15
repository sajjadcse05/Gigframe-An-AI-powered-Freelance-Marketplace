from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from jobs.models import Job, Proposal
from ai_engine.hybrid import rank_freelancers_for_job

User = get_user_model()

K_VALUES = [1, 3, 5]


class Command(BaseCommand):
    help = "Evaluates content-based, collaborative, and hybrid matching against real accepted-proposal history."

    def handle(self, *args, **options):
        # Only jobs where we actually know the "correct answer" — i.e.
        # someone was genuinely accepted — can be evaluated. This is
        # standard practice: you can only measure ranking quality
        # against outcomes you actually observed.
        accepted_proposals = Proposal.objects.filter(status="ACCEPTED").select_related("job", "freelancer")

        if accepted_proposals.count() < 3:
            self.stdout.write(self.style.WARNING(
                "Not enough accepted proposals to evaluate yet. Run seed_data first."
            ))
            return

        methods = ["content", "collaborative", "hybrid"]
        results = {method: {k: {"hits": 0, "total": 0} for k in K_VALUES} for method in methods}

        for proposal in accepted_proposals:
            job = proposal.job
            correct_freelancer = proposal.freelancer

            # The candidate pool: every freelancer who has EVER worked in
            # this job's category (a reasonable stand-in for "freelancers
            # who could plausibly have been matched to this job").
            candidates = User.objects.filter(role="FREELANCER", gigs__category=job.category).distinct()

            if correct_freelancer not in candidates:
                continue  # shouldn't happen with seed data, but guards against edge cases

            for method in methods:
                ranked = rank_freelancers_for_job(job, candidates, method=method)

                for k in K_VALUES:
                    top_k = ranked[:k]
                    results[method][k]["total"] += 1
                    if correct_freelancer in top_k:
                        results[method][k]["hits"] += 1

        # ---- Print the comparison table ----
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("MATCHING METHOD COMPARISON — Precision@K (Recall@K is equal here,")
        self.stdout.write("since each job has exactly one correct freelancer to find)")
        self.stdout.write("=" * 70)

        header = f"{'Method':<15}" + "".join(f"P@{k:<10}" for k in K_VALUES)
        self.stdout.write(header)
        self.stdout.write("-" * 70)

        for method in methods:
            row = f"{method:<15}"
            for k in K_VALUES:
                hits = results[method][k]["hits"]
                total = results[method][k]["total"]
                precision = hits / total if total > 0 else 0
                row += f"{precision:<12.2%}"
            self.stdout.write(row)

        self.stdout.write("=" * 70)
        self.stdout.write(f"Evaluated on {accepted_proposals.count()} accepted proposals (jobs with a known correct match).\n")