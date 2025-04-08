import logging
import regex

logger = logging.getLogger(__name__)

# Doing my best to avoid using a full-blown parser generator -- this requires regex instead of re. :-)
_KEY_REGEX = r"(?P<key>[a-zA-Z0-9_-]+)"
_VALUE_REGEX = r'"(?P<value>[a-zA-Z0-9_-]+)"'
_KV_REGEX = rf"(({_KEY_REGEX}\s*=\s*{_VALUE_REGEX})|({_VALUE_REGEX}\s*=\s*{_KEY_REGEX}))"
_AND_REGEX = r"AND|and"
_OR_REGEX = r"OR|or"
_OP_REGEX = rf"(?P<op>{_AND_REGEX}|{_OR_REGEX})"
_QUERY_REGEX = rf"^\s*{_KV_REGEX}\s*({_OP_REGEX}\s*{_KV_REGEX}\s*)*$"


class AnnotationPredicate:
    def __init__(self, query: str):
        query_pattern = regex.compile(_QUERY_REGEX)
        matches = query_pattern.match(query)
        if matches is None:
            raise ValueError(
                "Invalid query string for annotations! "
                """Please use the format 'KEY="VALUE" (AND|OR KEY="VALUE")*'."""
            )

        # Save our predicate.
        self.keys = list()
        self.values = list()
        self.operators = list()
        captures = matches.capturesdict()
        for k, v in zip(captures["key"], captures["value"], strict=False):
            logger.debug(f"Found key[{k}] = value[{v}] in (annotations) query string.")
            self.keys.append(k)
            self.values.append(v)
        for op in captures["op"]:
            logger.debug(f"Found operator op[{op}] in (annotations) query string.")
            self.operators.append(op.upper().strip())

    @property
    def disjuncts(self) -> list[dict[str, str]]:
        if any(x == "OR" for x in self.operators):
            key_iterator = iter(self.keys)
            value_iterator = iter(self.values)

            # AND binds tighter than OR, so first let's partition our operands by OR.
            partitions: list[dict[str, str]] = list()
            working_partition: dict[str, str] = {next(key_iterator): next(value_iterator)}
            for op in self.operators:
                match op:
                    case "AND":
                        working_partition[next(key_iterator)] = next(value_iterator)
                    case "OR":
                        partitions.append(working_partition)
                        working_partition = {next(key_iterator): next(value_iterator)}
                    case _:
                        raise AttributeError("Unexpected operation encountered!")
            partitions.append(working_partition)

            # Once partitioned, we can return our predicate in DNF (sum-product).
            return partitions

        else:
            # If we are given a full list of conjuncts, we can consolidate all of our key-values into a single dict.
            return [{k: v for k, v in zip(self.keys, self.values, strict=False)}]

    def __str__(self):
        return " OR ".join("(" + " AND ".join(f"{k} = '{v}'" for k, v in d.items()) + ")" for d in self.disjuncts)

    def __catalog_query_str__(self):
        return " OR ".join(
            "(" + " AND ".join(f"a.annotations.{k} = '{v}'" for k, v in d.items()) + ")" for d in self.disjuncts
        )
