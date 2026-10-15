"""The single refusal type for everything that tries to leave.

Every message is one plain sentence: what happened, and what to do next. None holds the blocked content."""

_MESSAGES = {
    "vault_name": "The message still contained a protected name or contact detail, so it was not sent; take it out and try again.",
    "raw_rows": "The message contained record-level data such as rows or a table, so it was not sent; ask for totals instead.",
    "bad_fact": "A figure was not in the allowed shape, so the message was not sent; send totals over groups of five or more.",
    "suppressed_figure": "A figure from a group smaller than five, or one without a group size, would have left, so nothing was sent; ask for a larger group.",
    "summary_too_long": "The document summary was too long, so it was not sent; shorten it to a few sentences.",
    "destination_not_allowed": "That destination is not on the allowed list, so nothing was sent; ask your administrator to add it if it is needed.",
    "internet_off": "Internet access is switched off for this module, so nothing was sent; ask your administrator to switch it on if it is needed.",
    "log_unavailable": "The record of outgoing calls could not be written, so nothing was sent; ask your administrator to check the company storage.",
    "transport_failed": "The call to the outside service could not be completed; please try again in a moment.",
    "no_credential": "No access key is set up for the provider, so nothing was sent; ask your administrator to add it.",
    "vault_unavailable": "The protected-names list could not be read, so nothing was sent; ask your administrator to check it and try again.",
    "bad_payload": "The message was not in a shape that can be sent, so nothing was sent; please try again with a plain question.",
    "payload_too_large": "The message was too long to send, so nothing was sent; shorten it and try again.",
    # AQF10-06: the provider's own answers, in words the administrator can act on
    "no_credit": "The model provider account is out of credit, so the model could not answer; ask the administrator to top it up.",
    "rate_limited": "The model provider is taking too many requests just now, so the model could not answer; please try again in a minute.",
    "provider_key_refused": "The model provider refused the access key, so the model could not answer; ask the administrator to check the key.",
    "model_unknown": "The model provider does not offer the model set up for this task; ask the administrator to check the model settings.",
    "daily_cap": "Today's model allowance for this demo is used up, so the agents answer from rules until tomorrow; nothing was sent to a model.",
    "provider_bad_request": "The model provider would not take the request, so the model could not answer; please try again with a shorter question.",
}


class EgressBlocked(Exception):
    """A call was refused. `message` is plain words and never holds the blocked content."""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        self.message = _MESSAGES.get(reason_code, "The call was refused, so nothing was sent; please try again.")
        super().__init__(self.message)
