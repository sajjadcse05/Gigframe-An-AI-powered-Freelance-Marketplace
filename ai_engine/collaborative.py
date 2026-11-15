from jobs.models import Proposal


def get_acceptance_rate(freelancer):
    """
    Collaborative filtering signal: what fraction of this freelancer's
    submitted proposals have historically been accepted? This reflects
    platform-wide hiring PATTERNS (which freelancers clients actually
    choose), rather than just matching text meaning — the defining
    trait of collaborative filtering vs. content-based approaches.

    Returns a score from 0 to 1. Freelancers with no proposals yet
    get a neutral 0.5 (neither penalized nor rewarded for having no
    track record) — this matters for the cold-start discussion.
    """
    proposals = Proposal.objects.filter(freelancer=freelancer)
    total = proposals.count()
    if total == 0:
        return 0.5

    accepted = proposals.filter(status="ACCEPTED").count()
    return accepted / total