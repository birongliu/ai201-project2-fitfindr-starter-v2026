"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import mcp_client
import config
import trace
import re
from tools import search_listings, suggest_outfit, create_fit_card
from generate import ModelUnavailable

_PRICE_REGEX = r"(?i)(?:(?:under|below|less than|max(?:imum)?|for)\s*\$?\s*|\$)\s*(\d+(?:\.\d+)?)"
_SIZE_PATTERN = r"(?:One\s+Size(?:\s*/\s*Oversized)?|W\d+(?:\s*L\d+)?|US\s+\d+(?:\.\d+)?|XXS|XS|XXL|XXXL|XL|S/M|M/L|L/XL|[SML]|\d+(?:\.\d+)?|small|medium|large|extra\s*large)"
_SIZE_PREFIX_REGEX = rf"(?i)\b(?:size|sz|fit)\s*[:=]?\s*({_SIZE_PATTERN})\b"
_SIZE_WORD_REGEX = r"(?i)\b(One\s+Size(?:\s*/\s*Oversized)?|XXS|XS|XXL|XXXL|XL|S/M|M/L|L/XL|[SML]|small|medium|large)\b"


def parse_query(query: str) -> dict:
    """
    Parse a user query into structured fields.
    
    Args:
        query: The user's query string.
        
    Returns:
        A dictionary with 'description', 'size', and 'max_price'.
    """
    price_match = re.search(_PRICE_REGEX, query)
    if price_match:
        price_str = price_match.group(1)
        max_price = float(price_str) if "." in price_str else int(price_str)
    else:
        max_price = None

    size_match = re.search(_SIZE_PREFIX_REGEX, query)
    if size_match:
        size = size_match.group(1)
    else:
        size_match = re.search(_SIZE_WORD_REGEX, query)
        size = size_match.group(1) if size_match else None

    description = re.sub(_PRICE_REGEX, "", query)
    if re.search(_SIZE_PREFIX_REGEX, description):
        description = re.sub(rf"(?i)\b(?:size|sz|fit)\s*[:=]?\s*{_SIZE_PATTERN}\b", "", description)
    elif size:
        description = re.sub(rf"(?i)\b{re.escape(size)}\b", "", description)

    description = re.sub(r"[,;]+", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    parsed = {
        "description": description,
        "size": size,
        "max_price": max_price,
    }
    return parsed

        
# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
    }


def _not_found_message(parsed: dict) -> str:
    """Return a user-friendly message when no results were found."""
    return f"No {parsed['description']} in size {parsed['size']} found for under ${parsed['max_price']}."

# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    ─────────────────────────────────────────────────────────────────────────
    TODO — build this, following the branch rule you wrote in Milestone 2.

      1. Start a session with new_session().

      2. Count the times round the loop, and call trace.check_iterations(count)
         on each one before you go again. It raises when the count passes
         MAX_ITERATIONS in config.py — see trace.py.

      3. Parse the query into a description, a size, and a max_price. Regex,
         string splitting, or asking the model are all fine — say which you
         chose in your README. Put the result in session["parsed"].

      4. Call search_listings() with what you parsed.
         Put the results in session["search_results"].

         ⚠️ THIS IS THE BRANCH. If nothing came back:
              - put a message in session["error"] saying what the user could
                change — "No results" is not that message
              - return the session
              - do NOT call suggest_outfit with nothing

      5. Choose an item — the first result is fine. Put it in
         session["selected_item"].

      6. Call suggest_outfit() with the selected item and the wardrobe.
         Put the result in session["outfit_suggestion"].

      7. Call create_fit_card() with the outfit and the item.
         Put the result in session["fit_card"].

      8. Return the session.

    ─────────────────────────────────────────────────────────────────────────
    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """
    session = new_session(query, wardrobe)

    iteration = 0

    iteration += 1

    trace.check_iterations(iteration)
    parsed = parse_query(query)
    session["parsed"] = parsed


    iteration += 1
    trace.check_iterations(iteration)
    search_results = mcp_client.call_tool("search_listings", {
        "description": parsed["description"],
        "size": parsed["size"],
        "max_price": parsed["max_price"]
    })

    if not search_results:
        session["error"] = _not_found_message(parsed)
        return session
    
    session["search_results"] = search_results

    iteration += 1
    trace.check_iterations(iteration)
    selected_item = search_results[0]
    session["selected_item"] = selected_item

    iteration += 1
    trace.check_iterations(iteration)
    outfit_suggestion = suggest_outfit(selected_item, wardrobe)

    if not outfit_suggestion:
        session["error"] = _not_found_message(parsed)
        return session

    session["outfit_suggestion"] = outfit_suggestion



    iteration += 1
    trace.check_iterations(iteration)
    fit_card = create_fit_card(outfit_suggestion, selected_item)
    if not fit_card:
        session["error"] = _not_found_message(parsed)
        return session

    session["fit_card"] = fit_card
    print(session)
    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
