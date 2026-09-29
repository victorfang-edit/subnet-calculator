"""Cross-check the hand-written bit math against Python's ipaddress module."""
import ipaddress
import random

import subnet as s


def test_against_stdlib_random():
    rng = random.Random(0)
    for _ in range(2000):
        ip, p = rng.getrandbits(32), rng.randint(0, 30)
        d = s.info(ip, p)
        ref = ipaddress.IPv4Network((ip, p), strict=False)
        assert d["network"] == int(ref.network_address)
        assert d["broadcast"] == int(ref.broadcast_address)
        assert d["mask"] == int(ref.netmask)
        assert d["usable"] == ref.num_addresses - 2


def test_slash31_and_32():
    assert s.info(s.ip_to_int("10.0.0.0"), 31)["usable"] == 2
    assert s.info(s.ip_to_int("10.0.0.5"), 32)["usable"] == 1


def test_mask_parsing():
    assert s.mask_to_prefix("255.255.255.192") == 26
    for bad in ("255.0.255.0", "255.255.255.256", "1.2.3"):
        try:
            s.mask_to_prefix(bad)
            assert False, bad
        except ValueError:
            pass


def test_private_and_class():
    assert s.is_private(s.ip_to_int("172.31.255.1")) and not s.is_private(s.ip_to_int("172.32.0.1"))
    assert s.ip_class(s.ip_to_int("192.168.1.1")) == "C"


def test_vlsm_fits_and_no_overlap():
    plan = s.vlsm(s.ip_to_int("192.168.1.0"), 24, [("A", 50), ("B", 25), ("C", 10), ("D", 2)])
    nets = [ipaddress.IPv4Network((n, p)) for _, _, n, p in plan]
    assert [n.prefixlen for n in nets] == [26, 27, 28, 30]
    for i, a in enumerate(nets):
        for b in nets[i + 1:]:
            assert not a.overlaps(b)
    for (_, hosts, n, p) in plan:
        assert s.info(n, p)["usable"] >= hosts


def test_vlsm_exact_boundaries():
    # 62 hosts fits a /26 exactly, 63 needs a /25
    assert s.vlsm(0, 16, [("x", 62)])[0][3] == 26
    assert s.vlsm(0, 16, [("x", 63)])[0][3] == 25


def test_split():
    subs = s.split(s.ip_to_int("10.0.0.0"), 24, 3)  # rounds up to 4
    assert [(s.int_to_ip(n), p) for n, p in subs][:2] == [("10.0.0.0", 26), ("10.0.0.64", 26)] and len(subs) == 4


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
    print("all tests passed")
