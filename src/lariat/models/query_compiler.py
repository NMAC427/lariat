from __future__ import annotations

import copy
from typing import Any

from .symbolic import FindOpExpression, Q, RawFindExpression


class QueryCompiler:
    def __init__(self, model):
        self.model = model
        self.params = {}
        self.counter = 0

    def _get_id(self):
        self.counter += 1
        return f"q{self.counter}"

    def compile(self, q: Q) -> tuple[str, dict[str, Any]]:
        # Convert to DNF (Disjunctive Normal Form)
        # Result is OR( AND(...), AND(...) )
        dnf = self.to_dnf(q)

        # If the top level is AND, wrap it in OR (single group)
        if isinstance(dnf, Q) and dnf.connector == Q.OR and not dnf.negated:
            groups = dnf.children
        else:
            groups = [dnf]

        # Process groups to extract positive and negative expressions
        processed_groups = []
        for group in groups:
            # Each group should be an AND of literals (or a single literal)
            # We flatten it just in case
            if isinstance(group, Q):
                group = self.flatten(group)

            pos_exprs = []
            neg_exprs = []

            children = group.children if isinstance(group, Q) else [group]

            for child in children:
                if isinstance(child, Q):
                    if child.negated:
                        # Handle negation of a literal (should be only one child if pushed down)
                        if not child.children:
                            continue
                        expr = child.children[0]
                        if isinstance(expr, FindOpExpression):
                            inv = self.invert_op(expr)
                            if inv:
                                pos_exprs.append(inv)
                            else:
                                # Cannot invert, so treat as Omit
                                neg_exprs.append(expr)
                        elif isinstance(expr, RawFindExpression):
                            # Cannot invert raw expression, treat as Omit
                            neg_exprs.append(expr)
                        else:
                            raise ValueError(f"Cannot negate {type(expr)}")
                    else:
                        # Nested Q that is not negated - should have been flattened but let's handle it
                        for subchild in child.children:
                            pos_exprs.append(subchild)
                else:
                    if isinstance(child, FindOpExpression) and child.op == "neq":
                        # Treat neq as !(eq)
                        eq_expr = FindOpExpression(child.lhs, "eq", child.rhs)
                        neg_exprs.append(eq_expr)
                    else:
                        pos_exprs.append(child)

            processed_groups.append(
                {"pos": pos_exprs, "neg": set(neg_exprs)}  # Use set for subset checking
            )

        # Sort groups by negation set size (descending)
        # This is a heuristic to try to satisfy the subset condition
        processed_groups.sort(key=lambda g: len(g["neg"]), reverse=True)

        # Validate subset condition: N(Gi) >= N(Gi+1)
        for i in range(len(processed_groups) - 1):
            current_neg = processed_groups[i]["neg"]
            next_neg = processed_groups[i + 1]["neg"]
            if not current_neg.issuperset(next_neg):
                raise ValueError(
                    "Cannot represent query: Negated conditions in OR branches must form a subset chain. "
                    "This limitation exists because FileMaker Omit requests apply to all preceding Find requests."
                )

        # Generate query string
        query_ids = []

        for group in processed_groups:
            pos_ids = []
            neg_ids = []

            for expr in group["pos"]:
                self.add_param(pos_ids, expr)

            # For negations, we only need to add the ones that are NOT present in the next group?
            # No, we need to add all negations for this group.
            # But wait, if we have G1 (neg {B, D}) and G2 (neg {B}).
            # Sequence: P1; !B; !D; P2; !B.
            # The second !B is redundant but harmless.
            # So we just output them.

            # However, we need to be careful about the order of !B and !D within the group?
            # It doesn't matter within the group.

            for expr in sorted(group["neg"], key=repr):
                self.add_param(neg_ids, expr)

            parts = []
            if pos_ids:
                parts.append(f"({','.join(pos_ids)})")

            for nid in neg_ids:
                parts.append(f"!({nid})")

            if parts:
                query_ids.append(";".join(parts))

        query_str = ";".join(query_ids)
        return query_str, self.params

    def flatten(self, q: Q) -> Q:
        if not isinstance(q, Q):
            return q

        new_children = []
        for child in q.children:
            if isinstance(child, Q):
                child = self.flatten(child)
                if child.connector == q.connector and not child.negated:
                    new_children.extend(child.children)
                else:
                    new_children.append(child)
            else:
                new_children.append(child)

        return Q(*new_children, _connector=q.connector, _negated=q.negated)

    def to_dnf(self, q: Q) -> Q:
        # Basic DNF conversion
        # 1. Push negations down (De Morgan)
        # 2. Distribute AND over OR

        if not isinstance(q, Q):
            return q

        # Step 1: Push negations
        q = self.push_negations(q)

        # Step 2: Distribute
        q = self.distribute(q)

        # Step 3: Flatten
        q = self.flatten(q)

        return q

    def push_negations(self, q: Q) -> Q:
        if not isinstance(q, Q):
            return q

        if q.negated:
            # De Morgan
            # ~(A & B) -> ~A | ~B
            # ~(A | B) -> ~A & ~B
            new_connector = Q.OR if q.connector == Q.AND else Q.AND
            new_children = []
            for child in q.children:
                if isinstance(child, Q):
                    new_child = copy.deepcopy(child)
                    new_child.negated = not new_child.negated
                    new_children.append(self.push_negations(new_child))
                else:
                    # Literal
                    # Wrap in Q and negate
                    new_children.append(Q(child, _negated=True))
            return Q(*new_children, _connector=new_connector)
        else:
            # Recurse
            new_children = [
                self.push_negations(c) if isinstance(c, Q) else c for c in q.children
            ]
            return Q(*new_children, _connector=q.connector)

    def distribute(self, q: Q) -> Q:
        if not isinstance(q, Q):
            return q

        # First distribute children
        new_children = [
            self.distribute(c) if isinstance(c, Q) else c for c in q.children
        ]
        q.children = new_children

        if q.connector == Q.AND:
            # Check if any child is OR
            # (A | B) & C -> (A & C) | (B & C)

            or_child_idx = -1
            for i, child in enumerate(q.children):
                if isinstance(child, Q) and child.connector == Q.OR:
                    or_child_idx = i
                    break

            if or_child_idx != -1:
                or_child = q.children[or_child_idx]
                others = q.children[:or_child_idx] + q.children[or_child_idx + 1 :]

                # Distribute
                new_or_children = []
                for item in or_child.children:
                    # item & others
                    # Create new AND group
                    # We need to be careful with recursion
                    new_and = Q(item, *others, _connector=Q.AND)
                    new_or_children.append(self.distribute(new_and))  # Recurse

                return Q(*new_or_children, _connector=Q.OR)

        return q

    def add_param(self, q_ids, expr):
        qid = self._get_id()
        q_ids.append(qid)

        if isinstance(expr, FindOpExpression):
            field_name = expr.lhs.name
            value = expr.lhs.to_filemaker(expr.rhs)

            op_map = {
                "eq": "=",
                "cn": "*{}*",
                "bw": "{}*",
                "ew": "*{}",
                "gt": ">",
                "gte": ">=",
                "lt": "<",
                "lte": "<=",
            }

            op = expr.op
            if op in op_map:
                prefix_or_fmt = op_map[op]
                if "{}" in prefix_or_fmt:
                    fm_value = prefix_or_fmt.format(value)
                else:
                    fm_value = f"{prefix_or_fmt}{value}"
            else:
                raise ValueError(f"Unsupported operator '{op}' in query expression.")

            self.params[f"-{qid}"] = field_name
            self.params[f"-{qid}.value"] = fm_value
        elif isinstance(expr, RawFindExpression):
            field_name = expr.field.name
            self.params[f"-{qid}"] = field_name
            self.params[f"-{qid}.value"] = expr.query

    def invert_op(self, expr: FindOpExpression) -> FindOpExpression | None:
        # Returns new expression or None
        mapping = {"neq": "eq", "gt": "lte", "gte": "lt", "lt": "gte", "lte": "gt"}
        if expr.op in mapping:
            return FindOpExpression(expr.lhs, mapping[expr.op], expr.rhs)
        return None
