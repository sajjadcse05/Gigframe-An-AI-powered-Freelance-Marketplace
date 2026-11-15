from .embeddings import compute_similarity


def rank_jobs_for_freelancer(freelancer, jobs_queryset, top_n=None):
    """
    Given a Freelancer and a queryset of open Jobs, returns those jobs
    sorted by semantic similarity to the freelancer's skills/bio —
    highest match first. This is the core "AI-recommended jobs" feature.
    """
    from ai_engine.embeddings import get_embedding

    profile_text = f"{freelancer.bio} Skills: {freelancer.skills}"
    profile_vector = get_embedding(profile_text)

    if profile_vector is None:
        return list(jobs_queryset)  # no bio/skills yet — nothing to compare against, return unranked

    scored = []
    for job in jobs_queryset:
        score = compute_similarity(profile_vector, job.embedding)
        scored.append((job, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    results = [job for job, score in scored]
    return results[:top_n] if top_n else results


def rank_gigs_for_client(client_job_text, gigs_queryset, top_n=None):
    """
    Given some text describing what a Client needs (e.g. their most
    recent job posting, or a search query) and a queryset of Gigs,
    returns gigs sorted by semantic similarity — the "AI Best Match"
    feature for Clients browsing gigs.
    """
    from ai_engine.embeddings import get_embedding

    query_vector = get_embedding(client_job_text)
    if query_vector is None:
        return list(gigs_queryset)

    scored = []
    for gig in gigs_queryset:
        score = compute_similarity(query_vector, gig.embedding)
        scored.append((gig, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    results = [gig for gig, score in scored]
    return results[:top_n] if top_n else results