class VariantNotFoundError(LookupError):
    def __init__(self, variant_id: str) -> None:
        self.variant_id = variant_id
        super().__init__(variant_id)


class InvalidVcfError(ValueError):
    pass
