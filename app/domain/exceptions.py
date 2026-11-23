class OversellError(Exception):
    def __init__(self, symbol: str, available: object, requested: object) -> None:
        self.symbol = symbol
        self.available = available
        self.requested = requested
        super().__init__(
            f"Oversell on {symbol}: available={available}, requested={requested}"
        )
