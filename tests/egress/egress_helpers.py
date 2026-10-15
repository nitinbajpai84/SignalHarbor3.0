import json

from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault

MODEL_HOST = "model.example.test"
MODEL_URL = f"https://{MODEL_HOST}/v1/messages"
NET_HOST = "public.example.test"


class Transport:
    """Stub transport: records every call, never touches the network."""

    def __init__(self, reply="ok"):
        self.calls = []
        self.reply = reply

    def __call__(self, url, body):
        self.calls.append((url, body))
        return self.reply


def make_gateway(plane, transport, internet_hosts=(NET_HOST,), policy_on=(), model_url=MODEL_URL,
                 internet_transport=None, model_allowlist=(MODEL_HOST,)):
    policy = EgressPolicy(plane)
    policy.set_internet_hosts(list(internet_hosts))
    for m in policy_on:
        policy.set_internet(m, True)
    vault = NameVault(plane)
    gw = EgressGateway(plane, vault, policy, model_allowlist=list(model_allowlist), model_url=model_url,
                       transport=transport, internet_transport=internet_transport or transport)
    return gw, vault, policy


def log_lines(plane):
    p = plane.area("context") / "egress_log.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []
