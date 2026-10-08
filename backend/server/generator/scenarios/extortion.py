"""Adult-site malvertising and sextortion.

The client got a threatening email: "I hacked your webcam while you watched
adult videos, pay in Bitcoin or I send the video to your contacts". It quotes
one of their real passwords, so it feels true. It isn't: the password comes
from an old breach, and nobody recorded anything.

What the client is embarrassed to say is how the crew got their email address
and card: days earlier they clicked an ad on an adult video site that sent
them to a fake "age verification" page, which took their email and card and
started a monthly charge. That is the part harder clients hide.

The player has to (1) prove the threat is a bluff with breach data, (2) follow
the Bitcoin demand and the "proof" link into the crew's infrastructure, and
(3) get the client to admit the ad click, or find the age-check site and the
card merchant without them. Both money streams cash out to the same wallet.

Content stays non-explicit: the site is only ever "an adult video site".
"""
from __future__ import annotations

from datetime import timedelta

from .. import fakes as F
from ..base import Scenario


class AdultAd(Scenario):
    key = "adult_ad"
    title = "Adult-site ad & sextortion"
    category = "extortion"
    real_world_basis = ("Malvertising on adult websites leads visitors to fake 'age verification' pages that take "
                        "their email and card; the same crews then send sextortion emails that quote a breached "
                        "password and demand Bitcoin.")
    player_skill = ("Prove the 'hacked webcam' threat is a bluff with breach data, trace the Bitcoin demand and the "
                    "'proof' link to the crew's infrastructure, and get the client to admit the ad click that gave "
                    "away their card.")
    report_fields = [("extortion_wallet", "Bitcoin wallet in the extortion email", "crypto_wallet"),
                     ("leaked_from", "Breach the quoted password came from", "breach"),
                     ("lure_domain", "Fake age-verification domain", "domain"),
                     ("payment_target", "Merchant account that charged the card", "payment_account"),
                     ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Staff member", "Graduate student", "Alumnus", "Adjunct instructor", "Lab technician"]

    def forum_bio(self):
        return "adult traffic (pops/redirects) + age-gate billing panels + bulk mailer. rev share, escrow only."

    def build(self):
        rng, w = self.rng, self.w

        # 1. the adult site and the ad network: real businesses whose ad slot was bought by the crew
        tube = rng.choice(["nightreel.example", "velvetstream.example", "afterdark-tube.example"])
        self.used_values.add(tube)
        tube_id = w.ent("domain", tube, verdict="benign", table="domains", fqdn=tube, registered_domain=tube,
                        created_on=self.at(-rng.randint(1500, 3000)).date(), popularity_rank=rng.randint(2000, 9000))
        tube_ip, _ = self.alloc_ip("hyperscale_cloud", "benign")
        w.edge(tube_id, tube_ip, "resolves_to", start=self.at(-900), source="DNSChronicle", confidence=2)
        adnet = "popverse-ads.example"
        adnet_id = w.ent("domain", adnet, verdict="benign", table="domains", fqdn=adnet, registered_domain=adnet,
                         created_on=self.at(-rng.randint(900, 2000)).date(), popularity_rank=rng.randint(9000, 40000))
        adnet_ip_id, adnet_ip = self.alloc_ip("hyperscale_cloud", "benign")
        w.edge(adnet_id, adnet_ip_id, "resolves_to", start=self.at(-700), source="DNSChronicle", confidence=2)
        self.herring(tube_id, "The adult website the victim was on. It displayed the ad; it did not run the scam.")
        self.herring(adnet_id, "Ad network whose ad slot the crew bought. Abused, not the operator.")

        # 2. the fake age-verification site (the crew's infrastructure)
        s = self.site("ageverify.example", title="Age Verification Required (18+)", path="/verify",
                      cdn_allowed=True, host_type="bulletproof", kit_pool=F.FAKE_AGEGATE_ARTIFACTS)
        self.conn.execute("update domains set is_typosquat_of=%s where entity_id=%s",
                          ("age-verification services", s.primary_id))
        self.slot("lure_domain", s.primary_id)

        click_at = self.at(-rng.uniform(1.5, 2.5))
        click_url = f"https://click.{adnet}/c?cid={F.token(rng, 10)}&zone={rng.randint(10000, 99999)}"
        click_id = self.mk_url(adnet_id, click_url, f"click.{adnet}", "suspicious")
        w.edge(tube_id, click_id, "serves_ad", start=self.at(-6), source="urlscope", confidence=2,
               note="ad slot on the video page")
        w.edge(click_id, s.landing_id, "redirects_to", start=self.at(-6), end=self.takedown, source="urlscope",
               confidence=2, note="HTTP 302 observed by scanner")
        click_scan = self.mk_scan(click_id, click_url, click_at + timedelta(hours=rng.randint(3, 20)), title="",
                                  ip=adnet_ip, final=s.landing_url, status=302,
                                  kit=["302 redirect from an ad-network click tracker", "campaign zone id in the query string"])
        self.support(click_scan, "Scan of the ad click: it redirects to the age-check page")

        # 3. the card merchant behind the "age check" (what shows on the bank statement)
        descriptor = f"AVS*VERIFYNOW {self.pretty(self.fict_number('888', toll_free=True))}"
        merchant = self.payment("card_merchant", "Lumen Billing Ltd", descriptor, holder="Lumen Billing Ltd",
                                verdict=self.fresh(), notes="Merchant account behind the age-check charges")
        w.edge(s.landing_id, merchant, "pays_to", start=click_at, source="Victim Report", confidence=1,
               note="card charged on the age-check form")
        self.slot("payment_target", merchant)

        # 4. the breach the quoted password really came from
        pw = rng.choice(F.OLD_PASSWORDS)
        victim_addr = self.email_addr(self.victim_email, verdict="benign")
        bid = self.conn.execute("select id from entities where kind='breach' and value like 'ShopLane%'").fetchone()[0]
        self.conn.execute("""insert into breach_records(breach_id, email, username, display_name, password_hash, hash_type,
                             signup_ip, case_id) values (%s,%s,%s,%s,%s,'md5',%s,%s)""",
                          (bid, self.victim_email, None, self.victim, F.fake_password_hash(rng, "md5"),
                           "192.0.2." + str(rng.randint(10, 250)), self.case_id))
        w.edge(victim_addr, bid, "leaked_in", source="BreachIndex", confidence=2)
        self.slot("leaked_from", bid)

        # 5. the sextortion email: From spoofed to the victim's own address, Bitcoin demand, "proof" link
        wallet = self.wallet("bitcoin", received=round(rng.uniform(800, 9000), 2))
        wallet_addr = self.value_of(wallet)
        self.slot("extortion_wallet", wallet)
        demand = rng.choice([1450, 1650, 1900, 2200])
        sib_id, sib_fqdn = s.siblings[0][0], s.siblings[0][1]
        proof_url = f"https://{sib_fqdn}/v/{F.token(rng, 8)}"
        proof_id = self.mk_url(sib_id, proof_url, sib_fqdn)
        proof_scan = self.mk_scan(proof_id, proof_url, self.at(hours=rng.randint(2, 30)),
                                  title="Private video: enter your access code", ip=s.second_ip,
                                  tracking=[(s.tid, s.tid_code)], jarm=s.jarm,
                                  kit=["countdown timer script", "no video file anywhere on the page",
                                       "Bitcoin address embedded in the page source"])
        self.support(proof_scan, "Scan of the 'proof' page: a countdown and no video")
        mdom, mip_id, mip = self.mail_domain(f"{rng.choice(['secure', 'mailer', 'notice'])}-{F.token(rng, 4)}.example",
                                             leak=self.p.require_person)
        self.support(mdom, "Sending domain of the extortion email")
        email = self.email_msg(
            subject=f"{self.victim_first}, {pw}",
            body=(f"Hello,\n\nI know that {pw} is one of your passwords. I put malware on the adult video site you "
                  f"visited. It turned on your webcam and recorded you, and I copied your contacts.\n\nSend "
                  f"${demand} in Bitcoin to this address:\n\n    {wallet_addr}\n\nYou have 48 hours. If I'm not paid, "
                  f"the video goes to everyone you know. You can see a preview here: {proof_url}\n\nDon't reply. This "
                  f"mailbox isn't monitored."),
            from_display=self.victim, from_addr=self.victim_email, envelope=f"bounce@{self.value_of(mdom)}",
            sending_ip=(mip_id, mip), sent=self.at(hours=-rng.uniform(1, 6)), dkim_domain=self.value_of(mdom),
            origin_client=self.origin_client(), label=f"Extortion email to {self.victim}")
        w.edge(email, wallet, "pays_to", source="Victim Report", confidence=1, note="Bitcoin address demanded in the email")
        w.edge(email, proof_id, "contains_link", source="Victim Report", confidence=1)
        w.edge(email, victim_addr, "impersonates", source="Internal SOC", confidence=1,
               note="From: header spoofed to the victim's own address")
        self.clue(email, "A threatening email that quotes a real password and demands Bitcoin")

        # 6. money: card payouts and the extortion wallet end up in the same cash-out wallet
        exch = self.payment("crypto_exchange", "Coinvale Exchange", f"acct-{F.token(rng, 6)}", verdict="suspicious")
        cash = self.wallet("bitcoin")
        self.conn.execute("update entities set verdict='suspicious', tags=array['cash-out'] where id=%s", (cash,))
        w.edge(merchant, exch, "transfers_to", start=self.at(-1), source="ScamWatch Portal", confidence=3,
               note="weekly merchant settlement")
        w.edge(exch, cash, "transfers_to", start=self.at(1), source="ChainScan", confidence=2)
        w.edge(wallet, cash, "transfers_to", start=self.at(2), source="ChainScan", confidence=2,
               note="consolidated with other victims' payments")
        self.support(exch, "Exchange account the card payouts moved through")

        self.complaints([merchant, s.primary_id],
                        ["Charged $39.99 a month by AVS*VERIFYNOW after an 'age check' pop-up I never meant to sign up for.",
                         "An ad on a video site said to verify I'm 18. It took my card and now there are monthly charges.",
                         "Same 'I recorded you' email as everyone else, with an old password of mine. Also an age-verify charge on my card."],
                        indicators=[s.primary_fqdn, descriptor], loss=(40, 400))
        self.complaints([wallet],
                        [f"Got the webcam email with my old password, demanding Bitcoin to {wallet_addr}. I almost paid.",
                         f"Sextortion email claiming a recording. It wanted Bitcoin sent to {wallet_addr}."],
                        indicators=[wallet_addr], n=2, loss=(0, 2200))

        self.hints = ["The email quotes a real password. Look the client's address up in Breach Lookup. Where could the "
                      "sender have gotten it?",
                      "Scan the 'preview' link. What else shares that page's fingerprints and certificate?",
                      "Ask the client about the charges on their card, and what they were doing when they first saw an "
                      "age check."]
        self.chain(email, "The extortion email")
        self.chain(wallet, "Bitcoin wallet the email demanded payment to")
        self.chain(victim_addr, "The client's own address, spoofed in the From line")
        self.chain(bid, "Old breach that leaked the quoted password: the threat is a bluff")
        self.chain(proof_id, "The 'preview' link in the email")
        self.chain(sib_id, "Domain hosting the 'preview' page")
        self.chain(s.cert_id, "Certificate linking the preview domain to the age-check domain")
        self.chain(s.primary_id, "Fake age-verification domain")
        self.chain(s.landing_id, "Fake age-verification page that took the card")
        self.chain(merchant, "Merchant account that charged the client's card")
        self.chain(cash, "Cash-out wallet both money streams end in")
        self.attribution([s.primary_id, wallet, merchant],
                         summary="Adult-traffic malvertising to fake age-verification billing pages, followed by mass "
                                 "sextortion emails demanding Bitcoin.",
                         targeting="adult-site visitors")
        self.chain(self.campaign_id, "Campaign")
        self.chain(self.actor_id, "Threat actor")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        self.fact("story", ["story"], f"I got an email saying someone hacked my webcam and recorded me, and they'll send the "
                  f"video to all my contacts unless I pay ${demand} in Bitcoin. It has one of my real passwords in it. "
                  f"I'm freaking out.")
        self.fact("when", ["when"], f"It came in {self.said(self.when_of(email))}. They gave me 48 hours.")
        self.fact("contact", ["contact"], "The weird part is it looks like it came from my own email address.",
                  keywords=["from", "sender", "address", "own"])
        self.fact("password", ["login"], f"The password in it, {pw}, is one I used years ago. I think it was for a shopping "
                  f"site. I don't use it anymore.", keywords=["password", "old", "shopping"])
        self.fact("webcam", ["device"], "I have a laptop with a webcam. I've put tape over it now.",
                  keywords=["webcam", "camera", "laptop", "computer", "malware", "virus", "recorded", "video", "recording"])
        self.fact("not_paid", ["amount"], "I haven't paid them anything. Should I?",
                  keywords=["bitcoin", "btc", "ransom", "demand", "pay", "paid", "send them", "sent them"])
        self.fact("adult_site", ["money", "link", "device"],
                  f"...Okay. I was on an adult video site, {tube}, and an ad said I had to verify I was over 18. It took "
                  f"me to a page that asked for my email and card number to confirm my age. A few days later there was a "
                  f"charge on my card from '{descriptor}'. That's probably how they got my email. Please don't put my "
                  f"name next to this in any report.", secret=True,
                  lie="There's nothing else. I have no idea how they got my email, and I definitely wasn't on any sites "
                      "like that.",
                  keywords=["adult", "porn", "porno", "xxx", "ad", "ads", "advert", "advertisement", "popup", "pop-up",
                            "age", "verify", "verification", "18", "site", "sites", "website", "browsing", "charge",
                            "charges", "card", "statement", "credit", "debit", "clicked", "click", "watching"],
                  unlocks=[tube_id, click_id, merchant],
                  proof=[s.primary_id, s.landing_id, s.landing_scan, click_id, click_scan, merchant])

        briefing = (f"{self.victim} ({self.victim_role}) received an email claiming their webcam was hacked and that a "
                    f"recording will go to their contacts unless they pay ${demand} in Bitcoin. It quotes one of their "
                    f"real passwords, and it appears to come from their own address. Decide whether the threat is real, "
                    f"trace the money, find the infrastructure behind it, and name who is responsible.")
        resolution = (f"The threat was a bluff: the quoted password came from the ShopLane 2021 breach, and the From line "
                      f"was spoofed. The 'preview' link sat on {sib_fqdn}, which shares a certificate and tracking ID with "
                      f"{s.primary_fqdn}, a fake age-verification page the client reached from an ad on {tube}. It took "
                      f"their email and card and billed them as '{descriptor}'. The card payouts and the Bitcoin demand "
                      f"cash out to the same wallet. Attributed to {self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution
