from lariat.core.query import FMQuery


def format_query(query: FMQuery) -> str:
    parts = []
    if query.command == "-findquery":
        q = query.params["-query"]
        qs = {}
        for i in range(100):
            q_key = f"-q{i+1}"
            if q_key in query.params:
                value_key = f"{q_key}.value"
                if value_key in query.params:
                    qs[q_key] = (query.params[q_key], query.params[value_key])

        parts.append(f"Command: {query.command}")
        parts.append(f"  -query: {q}")
        for k in sorted(qs.keys()):
            parts.append(f"  {k}: {qs[k]}")

    else:
        parts.append(f"Command: {query.command}")
        for k in sorted(query.field_params.keys()):
            parts.append(f"  {k}: {query.field_params[k]}")

    return "\n".join(parts)
