from symlog.souffle import (
    String,
    SymbolicString,
    SymbolicNumber,
    SymbolicNumberWrapper,
    SymbolicStringWrapper,
    Number,
    SYM,
    NUM,
    collect,
    Literal,
    Rule,
    Fact,
)
from symlog.utils import check_equality
from symlog.common import UNK_TYPE
from typing import List, Any, FrozenSet
from itertools import chain


class TypeAnalyser:
    __slots__ = ["declarations"]

    def __init__(self):
        self.declarations = {}

    def infer_declarations(self, rules: FrozenSet[Rule], facts: FrozenSet[Fact]):
        self.declarations = self._create_init_declarations(
            rules, facts
        )  # init declarations with UNK_TYPE

        self._infer_from_facts(facts)
        self._infer_from_rules(rules)

        return self.declarations

    def _create_init_declarations(self, rules: FrozenSet[Rule], facts: FrozenSet[Fact]):
        # get all literals from rules and facts
        literals = chain.from_iterable(
            collect(r, lambda x: isinstance(x, Literal)) for r in rules.union(facts)
        )

        # set the arg type of each literal according to the type of the arg
        declarations = {
            l.name: self._infer_declaration_types(l.args, raise_on_error=False)
            for l in literals
        }

        return declarations

    def _infer_from_facts(self, facts: FrozenSet[Fact]):
        def infer_from_fact(fact: Fact):
            head = fact.head
            decl_types = self._infer_declaration_types(head.args)

            # check if the inferred declaration is consistent with the new fact
            if not all(t == UNK_TYPE for t in self.declarations[head.name]):
                if not check_equality(decl_types, self.declarations[head.name]):
                    raise TypeError(
                        f"Declaration of relation {head.name} is inconsistent with the"
                        f" new fact {fact}."
                    )
            else:
                self.declarations[head.name] = decl_types

        for fact in facts:
            infer_from_fact(fact)

    def _infer_declaration_types(
        self, args: List[Any], raise_on_error=True
    ) -> List[str]:
        def get_type(arg: Any) -> str:
            if isinstance(arg, (String, SymbolicString, SymbolicStringWrapper)):
                return SYM
            elif isinstance(arg, (Number, SymbolicNumber, SymbolicNumberWrapper)):
                return NUM
            if raise_on_error:
                raise TypeError(
                    f"Type of {type(arg)} is invalid. Valid types: symbol, number"
                )
            return UNK_TYPE

        return list(map(get_type, args))

    def _infer_from_rules(self, rules: FrozenSet[Rule]):
        """Infers types of head args from body args."""

        is_changed = True
        while is_changed:
            is_changed = False
            for rule in rules:
                for idx, head_arg in enumerate(rule.head.args):
                    # Find inferred types from rule body literals
                    inferred_types = {
                        self.declarations[literal.name][literal.args.index(head_arg)]
                        for literal in rule.body
                        if head_arg in literal.args
                    }
                    inferred_types.discard(UNK_TYPE)

                    if not inferred_types:
                        continue

                    # If there's more than one unique type, it's ambiguous
                    if len(inferred_types) > 1:
                        raise TypeError(
                            f"Type of {head_arg} in {rule.head} is ambiguous"
                            f" in rule: {rule}"
                        )

                    # Extract single inferred type
                    inferred_type = next(iter(inferred_types))

                    # If the declaration for the current head arg is unknown or different from the inferred type,
                    # update the declaration and mark the change
                    current_decl = self.declarations[rule.head.name][idx]
                    if current_decl != inferred_type:
                        # If neither is UNK_TYPE, raise an error
                        if current_decl != UNK_TYPE and inferred_type != UNK_TYPE:
                            raise TypeError(
                                f"Type of {head_arg} in {rule.head} is ambiguous"
                                f" in rule: {rule}"
                            )
                        # If current declaration is UNK_TYPE, update it
                        elif current_decl == UNK_TYPE:
                            self.declarations[rule.head.name][idx] = inferred_type
                            is_changed = True
