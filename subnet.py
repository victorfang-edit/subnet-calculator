"""IPv4 subnet calculator + VLSM planner, written with plain bitwise math.

usage:
  python subnet.py info 192.168.10.77/26        (or 192.168.10.77 255.255.255.192)
  python subnet.py split 10.0.0.0/24 4
  python subnet.py vlsm 192.168.1.0/24 Sales:50 IT:25 Guest:10 WAN:2
"""
import os
import sys

COLOR = sys.stdout.isatty() or os.environ.get("FORCE_COLOR")
NET_C, HOST_C, DIM, RESET = ("\033[1;36m", "\033[1;33m", "\033[2m", "\033[0m") if COLOR else ("",) * 4


def ip_to_int(ip):
    parts = ip.split(".")
    if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        raise ValueError(f"invalid IPv4 address: {ip}")
    n = 0
    for p in parts:
        n = (n << 8) | int(p)
    return n


def int_to_ip(n):
    return ".".join(str((n >> s) & 255) for s in (24, 16, 8, 0))


def prefix_to_mask(prefix):
    if not 0 <= prefix <= 32:
        raise ValueError("prefix must be 0-32")
    return (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF


def mask_to_prefix(mask_str):
    m = ip_to_int(mask_str)
    prefix = bin(m).count("1")
    if prefix_to_mask(prefix) != m:
        raise ValueError(f"not a valid subnet mask (1s must be contiguous): {mask_str}")
    return prefix


def parse(cidr_or_ip, mask=None):
    if "/" in cidr_or_ip:
        ip, p = cidr_or_ip.split("/")
        return ip_to_int(ip), int(p)
    return ip_to_int(cidr_or_ip), mask_to_prefix(mask) if mask else 32


def info(ip, prefix):
    mask = prefix_to_mask(prefix)
    net = ip & mask
    bcast = net | (~mask & 0xFFFFFFFF)
    total = 2 ** (32 - prefix)
    if prefix == 32:
        first, last, usable = net, net, 1
    elif prefix == 31:  # RFC 3021 point-to-point: both addresses usable
        first, last, usable = net, bcast, 2
    else:
        first, last, usable = net + 1, bcast - 1, total - 2
    return {"address": ip, "prefix": prefix, "mask": mask, "wildcard": ~mask & 0xFFFFFFFF, "network": net,
            "broadcast": bcast, "first": first, "last": last, "total": total, "usable": usable}


def ip_class(ip):
    first = ip >> 24
    for limit, cls in ((127, "A"), (191, "B"), (223, "C"), (239, "D (multicast)")):
        if first <= limit:
            return cls
    return "E (reserved)"


def is_private(ip):
    return any((ip & prefix_to_mask(p)) == ip_to_int(n) for n, p in (("10.0.0.0", 8), ("172.16.0.0", 12), ("192.168.0.0", 16)))


def binary(n, prefix):
    out = ""
    for i, bit in enumerate(f"{n:032b}"):
        if i and i % 8 == 0:
            out += RESET + "."
        out += (NET_C if i < prefix else HOST_C) + bit
    return out + RESET


def split(net, prefix, count):
    """Split a network into `count` equal subnets (rounded up to a power of two)."""
    extra = (count - 1).bit_length()
    new_prefix = prefix + extra
    if new_prefix > 32:
        raise ValueError("network too small for that many subnets")
    size = 2 ** (32 - new_prefix)
    base = net & prefix_to_mask(prefix)
    return [(base + i * size, new_prefix) for i in range(2 ** extra)]


def vlsm(net, prefix, needs):
    """Variable Length Subnet Masking: biggest requirement first, each gets the smallest block that fits.
    needs = [(name, hosts)] -> [(name, hosts, network, prefix)]"""
    base = net & prefix_to_mask(prefix)
    end = base + 2 ** (32 - prefix)
    cursor, plan = base, []
    for name, hosts in sorted(needs, key=lambda x: -x[1]):
        if hosts < 1:
            raise ValueError(f"{name}: need at least 1 host")
        # smallest block with 2^n - 2 >= hosts (network + broadcast reserved)
        p = 32 - (hosts + 1).bit_length()
        if cursor + 2 ** (32 - p) > end:
            raise ValueError(f"out of address space at {name} ({hosts} hosts)")
        plan.append((name, hosts, cursor, p))
        cursor += 2 ** (32 - p)
    return plan


def cmd_info(args):
    ip, prefix = parse(*args)
    d = info(ip, prefix)
    rows = [("Address", int_to_ip(ip)), ("Network", f"{int_to_ip(d['network'])}/{prefix}"),
            ("Subnet mask", int_to_ip(d["mask"])), ("Wildcard mask", int_to_ip(d["wildcard"])),
            ("Broadcast", int_to_ip(d["broadcast"])), ("Host range", f"{int_to_ip(d['first'])} - {int_to_ip(d['last'])}"),
            ("Total addresses", f"{d['total']:,}"), ("Usable hosts", f"{d['usable']:,}"),
            ("Class", ip_class(ip)), ("Private (RFC 1918)", "yes" if is_private(ip) else "no")]
    for k, v in rows:
        print(f"  {k:<20}{v}")
    print(f"\n  {DIM}binary  ({NET_C}network bits{RESET}{DIM} | {HOST_C}host bits{RESET}{DIM}){RESET}")
    for label, val in (("Address", ip), ("Mask", d["mask"]), ("Network", d["network"]), ("Broadcast", d["broadcast"])):
        print(f"  {label:<11}{binary(val, prefix)}")


def cmd_split(args):
    net, prefix = parse(args[0])
    subs = split(net, prefix, int(args[1]))
    print(f"  {'#':<4}{'Subnet':<20}{'Host range':<34}{'Broadcast':<16}Hosts")
    for i, (n, p) in enumerate(subs, 1):
        d = info(n, p)
        rng = f"{int_to_ip(d['first'])} - {int_to_ip(d['last'])}"
        print(f"  {i:<4}{int_to_ip(n) + '/' + str(p):<20}{rng:<34}{int_to_ip(d['broadcast']):<16}{d['usable']}")


def cmd_vlsm(args):
    net, prefix = parse(args[0])
    needs = [(a.split(":")[0], int(a.split(":")[1])) for a in args[1:]]
    plan = vlsm(net, prefix, needs)
    print(f"  {'Name':<10}{'Need':>5}{'Subnet':>20}  {'Mask':<17}{'Usable':>7}  {'Gateway (1st host)':<18}{'Waste':>6}")
    used = 0
    for name, hosts, n, p in plan:
        d = info(n, p)
        used += d["total"]
        print(f"  {name:<10}{hosts:>5}{int_to_ip(n) + '/' + str(p):>20}  {int_to_ip(d['mask']):<17}{d['usable']:>7}  "
              f"{int_to_ip(d['first']):<18}{d['usable'] - hosts:>6}")
    total = 2 ** (32 - prefix)
    print(f"\n  Used {used} of {total} addresses ({used / total:.0%}); next free: {int_to_ip((net & prefix_to_mask(prefix)) + used)}")


def main(argv):
    if len(argv) < 2 or argv[0] not in ("info", "split", "vlsm"):
        print(__doc__)
        return 1
    try:
        {"info": cmd_info, "split": cmd_split, "vlsm": cmd_vlsm}[argv[0]](argv[1:])
    except (ValueError, IndexError) as e:
        print(f"error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
