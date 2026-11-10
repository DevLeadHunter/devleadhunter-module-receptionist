"""The rate limits of the receptionist's public routes (chat, leads, photos, checkouts, client space)."""

from services.rate_limiter import SlidingWindowRateLimiter

# 30 messages / 5 min per visitor per assistant: roomy for a real conversation, caps a bot.
assistant_chat_limiter = SlidingWindowRateLimiter(max_events=30, window_seconds=300)

# 8 leads / 5 min per visitor per assistant: a real visitor leaves one, this caps spam.
assistant_lead_limiter = SlidingWindowRateLimiter(max_events=8, window_seconds=300)

# 6 photos / 10 min per visitor per assistant: 3 per quote request, each one costs a vision call.
assistant_photo_limiter = SlidingWindowRateLimiter(max_events=6, window_seconds=600)

# 5 checkouts / 5 min per visitor per assistant: each click creates a Stripe session, this caps a bot.
assistant_subscribe_limiter = SlidingWindowRateLimiter(max_events=5, window_seconds=300)

# 120 client-space calls / 5 min per visitor: the page and its actions, far below a token guesser's needs.
assistant_client_limiter = SlidingWindowRateLimiter(max_events=120, window_seconds=300)

# 60 demo-space reads / 5 min per visitor: the page and its reloads, far below what guessing session ids needs.
assistant_demo_space_limiter = SlidingWindowRateLimiter(max_events=60, window_seconds=300)

# 3 fresh client-space links / hour per assistant, emailed to the business from an expired link.
assistant_client_renew_limiter = SlidingWindowRateLimiter(max_events=3, window_seconds=3600)

# 6 fresh client-space links / day per assistant: an old link replayed never floods the business.
assistant_client_renew_daily_limiter = SlidingWindowRateLimiter(max_events=6, window_seconds=86400)

# 2 test SMS / hour per assistant, from the client space: a mistyped number never drains the SMS budget.
assistant_client_test_sms_limiter = SlidingWindowRateLimiter(max_events=2, window_seconds=3600)

# 30 « marquer traitée » pages / 5 min per visitor: a signed link is opened once or twice, never dozens of times.
assistant_request_link_limiter = SlidingWindowRateLimiter(max_events=30, window_seconds=300)
