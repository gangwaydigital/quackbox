#!/usr/bin/env python3
"""Write a fully fictional demo mailbox (Harbor Lane Studios) as four .mbox files.
Usage: python3 scripts/make_demo_mbox.py OUT_DIR   (stdlib only, deterministic output)
Every person, company and address is invented; all domains are RFC 2606 .example.
"""
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr
from pathlib import Path
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
UTC = timezone.utc
rng = random.Random(20240601)
HL = "harborlane.example"

# key: (name, address, title)
P = {
    "dana": ("Dana Whitfield", f"dana.whitfield@{HL}", "Head of Operations"),
    "marcus": ("Marcus Bell", f"marcus.bell@{HL}", "Production Lead"),
    "jordan": ("Jordan Avery", f"jordan.avery@{HL}", "Project Coordinator"),
    "jo_home": ("Jo Avery", "jo.avery@homemail.example", ""),
    "priya": ("Priya Raman", f"priya.raman@{HL}", "Creative Director"),
    "tomas": ("Tomas Lindqvist", f"tomas.lindqvist@{HL}", "Lead Engineer"),
    "hana": ("Hana Mori", f"hana.mori@{HL}", "Senior Designer"),
    "elena": ("Elena Voss", f"elena.voss@{HL}", "Finance Manager"),
    "samir": ("Samir Haddad", f"samir.haddad@{HL}", "Sales Lead"),
    "chloe": ("Chloe Bennett", f"chloe.bennett@{HL}", "Marketing Manager"),
    "ravi": ("Ravi Patel", f"ravi.patel@{HL}", "Software Engineer"),
    "naomi": ("Naomi Clarke", f"naomi.clarke@{HL}", "People Partner"),
    "oscar": ("Oscar Finch", f"oscar.finch@{HL}", "Office Manager"),
    "lucia": ("Lucia Ferrer", f"lucia.ferrer@{HL}", "Account Manager"),
    "ben": ("Ben Okoye", f"ben.okoye@{HL}", "Junior Designer"),
    "grace": ("Grace Tan", f"grace.tan@{HL}", "Founder and CEO"),
    # outside parties
    "callum": ("Callum Reyes", "callum.reyes@brightwave.example", "Brand Director, Brightwave Outdoor"),
    "ingrid": ("Ingrid Solberg", "ingrid.solberg@tidemark.example", "Account Rep, Tidemark Print & Freight"),
    "walter": ("Walter Pruitt", "walter.pruitt@cedarpoint.example", "Property Manager, Cedar Point Estates"),
    "fiona": ("Fiona Marsh", "fiona.marsh@fieldnote.example", "Recruiter, Fieldnote Talent"),
    "pat": ("Pat Lorimer", "pat.lorimer@kestrelbank.example", "Business Banking, Kestrel Bank"),
    "theo": ("Theo Brandt", "theo.brandt@mail.example", ""),
    "nia": ("Nia Castellanos", "nia.castellanos@mail.example", ""),
    "dw": ("Design Weekly", "hello@designweekly.example", ""),
    "ct": ("Cloud Toolbox Digest", "digest@cloudtoolbox.example", ""),
}
STAFF = ["dana", "marcus", "jordan", "priya", "tomas", "hana", "elena", "samir", "chloe", "ravi",
         "naomi", "oscar", "lucia", "ben", "grace"]
FIRST = {k: v[0].split()[0] for k, v in P.items()}
FIRST["jo_home"] = "Jo"

MAILBOXES = ["Inbox", "Sent", "Projects", "Archive"]
MSGS = []  # every message dict, in creation order


def ts(y, m, d, hh=9, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=PT)


def mid():
    return f"{rng.getrandbits(64):016x}.{rng.getrandbits(24):06x}@{HL}"


def add(when, frm, to, subject, body, cc=(), bcc=(), parent=None, topic="misc", attach=(), invite=None,
        html=None, extra=None, box=None, no_mid=False):
    """Create one message; `parent` is another message dict (sets In-Reply-To/References)."""
    m = dict(when=when, frm=frm, to=list(to), cc=list(cc), bcc=list(bcc), subject=subject, body=body,
             topic=topic, attach=list(attach), invite=invite, html=html, extra=extra or {}, box=box,
             mid=None if no_mid else mid(), refs=[], irt=None)
    if parent:
        m["irt"] = parent["mid"]
        m["refs"] = parent["refs"] + [parent["mid"]]
    MSGS.append(m)
    return m


# ---------- attachments ----------
def tiny_pdf(title, lines):
    """Minimal one-page PDF with real text so pypdf can extract it."""
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    text = "BT /F1 12 Tf 54 740 Td 16 TL (%s) Tj\n" % esc(title)
    text += "".join("T* (%s) Tj\n" % esc(l) for l in lines) + "ET"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(text), text.encode()),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    return out


def csv_att(name, header, rows):
    return (name, "text/csv", "\n".join([",".join(header)] + [",".join(map(str, r)) for r in rows]) + "\n")


def txt_att(name, text):
    return (name, "text/plain", text + "\n")


def pdf_att(name, title, lines):
    return (name, "application/pdf", tiny_pdf(title, lines))


# ---------- calendar ----------
def ics(uid, summary, start, end, org, atts, loc, desc, method="REQUEST", allday=False, rrule=None,
        status="CONFIRMED", partstat="NEEDS-ACTION"):
    esc = lambda s: s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    if allday:
        ds, de = f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{(end or start) + timedelta(days=1):%Y%m%d}"
    else:
        f = lambda d: d.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        ds, de = f"DTSTART:{f(start)}", f"DTEND:{f(end)}"
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Harbor Lane Studios//Demo//EN", f"METHOD:{method}",
         "BEGIN:VEVENT", f"UID:{uid}@{HL}", "DTSTAMP:20240101T000000Z", ds, de, f"SUMMARY:{esc(summary)}",
         f"DESCRIPTION:{esc(desc)}", f"LOCATION:{esc(loc)}", f'ORGANIZER;CN="{P[org][0]}":mailto:{P[org][1]}']
    if rrule:
        L.append(f"RRULE:{rrule}")
    for a in atts:
        L.append(f'ATTENDEE;CN="{P[a][0]}";ROLE=REQ-PARTICIPANT;PARTSTAT={partstat}:mailto:{P[a][1]}')
    L += [f"STATUS:{status}", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(L) + "\r\n"


def invite(sent, org, atts, summary, start, hours, loc, desc, mode="inline", **kw):
    uid = f"evt-{rng.getrandbits(40):010x}"
    end = None if kw.get("allday") else start + timedelta(hours=hours)
    body_ics = ics(uid, summary, start, end, org, atts, loc, desc, **kw)
    when = start.strftime("%A %B %d at %H:%M") if not kw.get("allday") else start.strftime("%A %B %d (all day)")
    text = f"{P[org][0]} invited you to: {summary}\n\nWhen: {when}\nWhere: {loc}\n\n{desc}\n"
    return add(sent, org, atts, f"Invitation: {summary}", text, topic="invite", invite=(body_ics, mode, kw.get("method", "REQUEST")))


# ---------- thread machinery ----------
WORKDAY = lambda d: d + timedelta(days=(7 - d.weekday()) % 7 if d.weekday() >= 5 else 0)


def when_in(a, b):
    """Random weekday business-hours moment between two dates."""
    d = a + timedelta(days=rng.randrange((b - a).days))
    d = WORKDAY(d)
    return d.replace(hour=rng.randrange(8, 18), minute=rng.randrange(0, 60))


SIGN = ["Thanks,", "Best,", "Cheers,", "Thank you,", "Regards,", "Talk soon,"]
HI = ["Hi {n},", "Hey {n},", "{n},", "Morning {n},", "Hi all,"]


def wrap(frm, to_first, text, quoted=None):
    s = rng.choice(HI).format(n=to_first) + "\n\n" + text + "\n\n" + rng.choice(SIGN) + "\n" + FIRST[frm]
    if rng.random() < 0.35 and P[frm][2]:
        s += f"\n{P[frm][2]}, Harbor Lane Studios"
    if quoted:
        q = [l for l in quoted["body"].split("\n") if l.strip() and not l.startswith(">")][1:5]
        s += f"\n\nOn {quoted['when']:%a, %b %d, %Y}, {P[quoted['frm']][0]} wrote:\n" + "\n".join("> " + l for l in q)
    return s


# topic -> (window, cast, [(subject, thing, opener)], replies)
T = {}
T["launch"] = dict(
    win=((2023, 2, 1), (2024, 6, 30)), cast=["chloe", "priya", "tomas", "ravi", "hana", "samir", "dana", "grace", "ben"],
    subj=[
        ("Tidewatch 2.0 launch date", "the launch date", "We need to lock the Tidewatch 2.0 launch date so marketing can book the newsletter slots. Engineering says the tide-table sync is the last open item."),
        ("Beta tester recruitment", "the beta list", "We have 140 sign-ups for the Tidewatch beta. Can we cap it at 100 and keep the rest for the second wave?"),
        ("App Store listing copy", "the store listing", "Draft listing copy for Tidewatch 2.0 is in the shared folder. Title, subtitle and the first three screenshots need sign-off."),
        ("Press kit for Tidewatch", "the press kit", "I am assembling the press kit: logo pack, three screenshots, a founder quote and a one-page fact sheet."),
        ("Launch week social calendar", "the social calendar", "Here is a first pass at the launch-week social calendar. Posts go out at 8am Pacific with a harbor photo each day."),
        ("Pricing for the Pro tier", "Pro tier pricing", "We have to decide the Pro tier price. Options on the table are 3.99 monthly or 29.99 yearly with a one-week trial."),
        ("TestFlight build 2.0.0 (14) feedback", "build 14", "Build 14 is out to testers. Please collect crash reports and the tide-chart rendering complaints in one place."),
        ("Tidewatch landing page copy", "the landing page", "Landing page copy needs one more pass. The hero line still reads like a spec sheet instead of a promise."),
        ("Release notes for 2.0", "the release notes", "Release notes draft is ready. We should lead with offline tide tables and mention the new widget."),
        ("Widget design review", "the home screen widget", "Hana's widget mockups are ready. Small and medium sizes show next high tide, large adds the wind arrow."),
        ("Launch video script", "the launch video", "Script for the 45 second launch video is attached below. One location, two actors, no voiceover."),
        ("Support macros for launch week", "the support macros", "We should prepare canned replies for the five questions we expect: subscriptions, widgets, offline mode, units, refunds."),
        ("Localization for the French and Spanish listings", "the translations", "Translations for the French and Spanish store listings came back. Someone fluent should proofread before we submit."),
        ("Post-launch metrics review", "launch metrics", "One week after launch: downloads, trial starts and day-1 retention are in the dashboard. Let's review Thursday."),
        ("Tidewatch 2.1 scope", "the 2.1 scope", "Time to scope 2.1. Candidates are tide alerts, a Watch complication and shareable trip plans."),
    ],
    rep=[
        "I looked at {thing} this morning and I think we are close. Two small items remain and I will have them done by {day}.",
        "Agreed on {thing}. Let's not add anything new before {day}; the schedule has no slack left.",
        "Quick update on {thing}: I sent the latest to the group and flagged the open question about wording.",
        "Can we get a decision on {thing} by {day}? Everything downstream is waiting on it.",
        "Thanks for pulling {thing} together. A few comments inline in the document, nothing blocking.",
        "I would push back slightly on {thing}. The user research says people care more about reliability than novelty.",
        "{thing}: ticket {tk} is now closed and verified on two devices. Moving on to the next item.",
        "Looping in the rest of the team so everyone has the same view of {thing}. Please reply-all with concerns.",
        "Good call. For {thing}, I suggest we do a final check on {day} and freeze after that.",
        "Nice work on {thing}. Sharing it with Grace for a last look before we publish.",
    ])
T["budget"] = dict(
    win=((2023, 1, 1), (2024, 12, 20)), cast=["elena", "dana", "grace", "samir", "pat", "lucia", "ingrid", "chloe"],
    subj=[
        ("Q1 budget review", "the Q1 budget", "Attached is the Q1 budget versus actuals. Software and contractor spend are over; travel is well under."),
        ("Invoice 2041 from Tidemark Print & Freight", "invoice 2041", "Invoice 2041 for the printed packaging proofs came in at the quoted amount. Needs approval before Friday's payment run."),
        ("Software license renewals", "the license renewals", "Eleven software subscriptions renew next month. I listed them with cost per seat; please mark what we can drop."),
        ("Expense report reminder", "expense reports", "Reminder that expense reports for the month are due the 5th. Receipts must be attached or I cannot reimburse."),
        ("Brightwave milestone invoice", "the milestone invoice", "Milestone 2 for Brightwave is complete, so I can send the invoice. Can you confirm the deliverables are accepted?"),
        ("Monthly bank reconciliation", "the reconciliation", "Reconciliation is done except for two unmatched deposits. I will chase the bank for details."),
        ("Annual budget planning kickoff", "next year's budget", "It is time to start next year's budget. Please send your headcount and spend assumptions by the end of the month."),
        ("Purchase order for new monitors", "the monitor order", "Purchase order for six studio monitors is ready. Total is under the approval limit, so this just needs a second pair of eyes."),
        ("Overdue invoice reminder", "the overdue invoice", "Invoice 1987 is 20 days past due. I drafted a polite reminder; shall I send it or would you rather call?"),
        ("Payroll calendar changes", "the payroll calendar", "Payroll dates shift by a day around the holidays. The updated calendar is in the finance folder."),
        ("Travel budget for the design conference", "the conference travel", "Priya and Hana want to attend the design conference in spring. Estimated cost for both is in the attached sheet."),
        ("Cash flow forecast", "the cash forecast", "Updated cash flow forecast attached. We are comfortable through the year but the March payments are tight."),
        ("Bank fee review", "the bank fees", "Our monthly bank fees went up. I would like to ask Kestrel Bank about moving to the lower tier."),
        ("Year-end finance close checklist", "the year-end close", "Year-end close checklist is attached. Please clear your open expenses and purchase orders before the cutoff."),
    ],
    rep=[
        "Thanks. I checked {thing} against the ledger and the numbers tie out. Ref {tk}.",
        "Can you send the supporting detail for {thing}? Finance needs it for the file.",
        "Approved on my side for {thing}. Elena, please go ahead.",
        "I have a question about {thing}: is the amount before or after tax?",
        "Updated {thing} with the corrections and re-attached. The total changed by {amt}.",
        "For {thing} I would hold until the next cycle; we do not need it this month.",
        "Confirming {thing} will be paid on {day}. I will send the remittance advice afterwards.",
        "The variance on {thing} is {amt}. Mostly timing, nothing unusual.",
        "Noted on {thing}. I will adjust the forecast and share the new version by {day}.",
        "Thanks all, {thing} is closed from my end.",
    ])
T["hiring"] = dict(
    win=((2023, 2, 1), (2024, 10, 15)), cast=["naomi", "marcus", "priya", "tomas", "fiona", "grace", "dana", "hana"],
    subj=[
        ("Senior Designer opening", "the Senior Designer role", "The Senior Designer role is approved. Draft job description is attached; please comment on the must-have list."),
        ("Candidate shortlist: product designer", "the shortlist", "Fieldnote sent a shortlist of four product designers. Resumes are attached for review."),
        ("Interview schedule for Nia Castellanos", "Nia's interview", "Nia Castellanos is available for a panel interview next week. Can everyone block ninety minutes?"),
        ("Interview feedback: Theo Brandt", "Theo's feedback", "Please add your interview feedback for Theo Brandt to the shared form before the debrief."),
        ("Offer letter draft", "the offer letter", "Offer letter draft for the engineering hire is attached. Salary band and start date are filled in; please check the wording."),
        ("Onboarding plan for new starters", "the onboarding plan", "I put together a two week onboarding plan: equipment, buddy, first project and a check-in each Friday."),
        ("Referral program for open roles", "the referral bonus", "To widen the pipeline I suggest a small referral bonus for the open roles. Thoughts?"),
        ("Junior engineer take-home task", "the take-home task", "Draft take-home task for the junior engineer opening. It should take two hours at most."),
        ("Job posting performance", "the job posting", "The job posting has had 300 views and 12 applications this week. Should we boost it or change the title?"),
        ("Intern program for summer", "the summer interns", "We could host two interns this summer if someone can mentor. Looking for volunteers."),
        ("Recruiter agreement terms", "the recruiter terms", "Fieldnote sent their standard terms. The fee is 18 percent; I would like to try for 15."),
        ("Reference checks", "the reference checks", "Reference checks for the finalist came back positive. Details are in the hiring folder."),
        ("Team lunch with candidate", "the candidate lunch", "We should take the finalist to lunch on their second visit. Oscar, can you book somewhere quiet?"),
    ],
    rep=[
        "On {thing}: I can do {day} afternoon or any morning before that.",
        "Thanks for sending {thing}. My feedback is in the document; overall I am positive.",
        "I would like to see a portfolio walkthrough as part of {thing}. Fifteen minutes is enough.",
        "Let's keep {thing} confidential until we have a decision. Please do not forward.",
        "Updated {thing} with the comments from the group. Final version attached to ticket {tk}.",
        "I disagree slightly on {thing}; we should weigh collaboration skills more than tool experience.",
        "Calendar invite for {thing} is out. Let me know if the time conflicts with anything.",
        "Naomi, can you confirm the process for {thing}? I want to be sure we are consistent.",
        "Good progress on {thing}. Debrief on {day} and then we decide.",
        "Candidate responded about {thing} and is happy to proceed.",
    ])
T["move"] = dict(
    win=((2023, 6, 1), (2024, 1, 31)), cast=["oscar", "dana", "grace", "walter", "ingrid", "tomas", "hana", "priya"],
    subj=[
        ("Pier 9 lease terms", "the lease terms", "Cedar Point Estates sent the lease draft for the Pier 9 warehouse unit. Summary of terms is attached."),
        ("Moving day schedule", "moving day", "Draft schedule for moving day: IT packs at 7am, furniture at 9am, the truck arrives at 1pm."),
        ("Furniture order for the new office", "the furniture order", "Furniture quotes are in. The standing desks cost more but the team asked for them in the survey."),
        ("Internet install at Pier 9", "the internet install", "The internet provider can install fiber on the 10th. Someone needs to be on site to let them in."),
        ("Parking and keys", "keys and parking", "Walter confirmed we get six parking permits and twelve keys. Who needs a permit?"),
        ("Address change checklist", "the address change", "Checklist for the address change: bank, insurance, domain registrar, business cards, website footer."),
        ("Floor plan options", "the floor plan", "Two floor plan options are attached. Option B puts the studio near the loading door and the quiet room by the windows."),
        ("Packing boxes and labels", "the packing boxes", "Boxes arrive Tuesday. Please label by team color and keep monitors in their original foam."),
        ("Pier 9 walkthrough", "the walkthrough", "Walter can show us the unit on Thursday. We should bring a tape measure and the floor plan."),
        ("Old office handover", "the old office handover", "The landlord will inspect the old office after we leave. Oscar is making a list of wall patches."),
        ("Network cabling quote", "the cabling quote", "Cabling quote for the new office came in at a reasonable price. Includes eight drops and a patch panel."),
        ("Office plants and kitchen supplies", "the kitchen setup", "Small but morale-relevant: kitchen supplies, coffee machine and plants for the new space."),
        ("Move budget tracker", "the move budget", "I started a spreadsheet to track every cost of the move against the approved budget."),
    ],
    rep=[
        "Regarding {thing}: I confirmed with the vendor and we are on track for {day}.",
        "Can we get {thing} in writing? I would prefer not to rely on a phone call.",
        "Thanks Oscar, {thing} looks good to me. One question about the timing on {day}.",
        "I added {thing} to the shared checklist, item {tk}.",
        "For {thing}, the cost came in {amt} under the estimate.",
        "Flagging that {thing} overlaps with the client review. Can we shift by a day?",
        "Walter replied about {thing}; he is fine with the proposal and will send paperwork.",
        "Let's make a decision on {thing} this week. Everything else depends on it.",
        "Reminder to everyone: please confirm {thing} by {day}.",
        "Update on {thing}: done and photographed. Pictures are in the move folder.",
    ])
T["client"] = dict(
    win=((2023, 9, 1), (2024, 11, 15)), cast=["lucia", "callum", "priya", "hana", "ben", "marcus", "dana", "grace", "jordan"],
    subj=[
        ("Brightwave rebrand: kickoff notes", "the kickoff", "Thanks for the great kickoff. Notes and next steps for the Brightwave Outdoor rebrand are below."),
        ("Logo concepts round 1", "the logo concepts", "Round 1 logo concepts attached: three directions, from a mountain mark to a wordmark with a trail line."),
        ("Brand guidelines draft", "the guidelines", "First draft of the brand guidelines: color, type, spacing and photography rules."),
        ("Packaging mockups", "the packaging mockups", "Packaging mockups for the trail bottle and the daypack tag are ready for review."),
        ("Feedback on the color palette", "the palette", "Our team loves the forest green but finds the orange too loud. Could you try a softer ember tone?"),
        ("Photoshoot planning", "the photoshoot", "Photoshoot is booked for two days at the lake. Shot list and model call sheet are attached."),
        ("Website refresh scope", "the website scope", "Brightwave wants the site refreshed after the rebrand. Rough scope and estimate are attached."),
        ("Revision round 2", "revision round 2", "Revision round 2 incorporates the palette changes and a simplified wordmark. Please review by Friday."),
        ("Social templates", "the social templates", "Social media templates are done: story, square and cover formats in both color modes."),
        ("Approval for final artwork", "final artwork", "Please confirm final artwork approval in writing so we can release files to the printer."),
        ("Print proofs", "the print proofs", "Print proofs arrived from Tidemark. Colors are close but the green on the tags runs slightly dark."),
        ("Brightwave signage files", "the signage files", "Signage files exported in the three required sizes. Naming follows the agreed convention."),
        ("Project retrospective", "the retrospective", "Now that the rebrand is wrapping up, I would like a short retrospective with the Brightwave team."),
        ("Brand asset handover", "the asset handover", "Final asset handover: master files, fonts, guidelines PDF and a short usage video."),
    ],
    rep=[
        "Thanks for the update on {thing}. We will review internally and respond by {day}.",
        "Looks great. On {thing} we have two small comments, listed below.",
        "Could we schedule a short call about {thing}? Easier to talk through than email.",
        "Understood on {thing}. Updated files are uploaded to the shared folder, version {tk}.",
        "I think {thing} is nearly there. One change to the spacing and we can call it done.",
        "Just checking in on {thing}; the printer needs an answer by {day}.",
        "Confirming {thing} is approved from our side. Thank you for the quick turnaround.",
        "Hana made the changes for {thing}; please check the export before it goes out.",
        "A note on {thing}: our brand checklist says the tagline must stay as written.",
        "We are happy with {thing}. Please send the invoice for this milestone.",
    ])

# who writes the first reply to whom is random within the cast; some externals only appear in their topic
EXT = {"callum", "ingrid", "walter", "fiona", "pat"}


def day_phrase(d):
    return (d + timedelta(days=rng.randrange(2, 9))).strftime("%A %b %d")


def attachment_for(topic, d):
    r = rng.random()
    if topic == "budget":
        if r < 0.45:
            n = rng.randrange(6, 14)
            return [csv_att(f"budget-{d:%Y-%m}.csv", ["Category", "Budget", "Actual", "Variance"],
                            [(c, b := rng.randrange(2, 40) * 500, a := b + rng.randrange(-4, 6) * 250, a - b)
                             for c in ["Software", "Contractors", "Travel", "Equipment", "Marketing", "Rent", "Training",
                                       "Insurance", "Supplies", "Events", "Misc", "Utilities", "Fees"][:n]])]
        if r < 0.7:
            no = rng.randrange(1000, 3000)
            return [pdf_att(f"invoice-{no}.pdf", f"Invoice {no}", [f"Date: {d:%Y-%m-%d}", "Bill to: Harbor Lane Studios",
                    f"Amount due: {rng.randrange(8, 90) * 100}.00 USD", "Terms: net 30", "Thank you for your business."])]
    elif topic == "client" and r < 0.3:
        return [pdf_att(f"brand-guidelines-v{rng.randrange(1, 4)}.pdf", "Brightwave Outdoor Brand Guidelines (draft)",
                        ["Primary color: forest green", "Secondary color: ember", "Typeface: a friendly geometric sans",
                         "Logo clear space: height of the B", "Photography: natural light, real trails"])]
    elif topic == "hiring" and r < 0.25:
        return [txt_att("job-description.txt", "Senior Designer, Harbor Lane Studios\n\nYou will lead visual design for client and product work.\nMust have: 5 years of product design, strong portfolio, clear communication.\nNice to have: motion, prototyping.")]
    elif topic == "move" and r < 0.35:
        return [csv_att("move-schedule.csv", ["Time", "Task", "Owner"],
                        [("07:00", "Pack IT equipment", "Tomas"), ("09:00", "Move furniture", "Oscar"),
                         ("13:00", "Truck arrives at Pier 9", "Oscar"), ("15:00", "Set up network", "Tomas")])]
    elif topic == "launch" and r < 0.3:
        return [txt_att("release-notes.txt", "Tidewatch 2.0\n\n- Offline tide tables for 600 harbors\n- New home screen widget\n- Faster chart rendering\n- Fixed a crash when changing units")]
    return []


def build_thread(topic, spec, start, jordan_chance=0.0):
    cfg = T[topic]
    subject, thing, opener = spec
    cast = list(cfg["cast"])
    if topic != "client" and "jordan" in cast:
        cast.remove("jordan")
    ext = [c for c in cast if c in EXT]
    internal = [c for c in cast if c not in EXT]
    n = rng.choice([1, 2, 2, 3, 3, 3, 4, 4, 5, 6, 7])
    others = rng.sample(internal, 3) + (rng.sample(ext, 1) if ext and rng.random() < 0.6 else [])
    if "dana" in internal and "dana" not in others and rng.random() < 0.7:
        others.append("dana")
    if topic == "client" and "jordan" not in others and rng.random() < jordan_chance:
        others.append("jordan")
    people = others[:]
    first, rest = people[0], people[1:]
    to = rest[:rng.choice([1, 2])] or rest[:1]
    cc = [p for p in rest if p not in to][:2]
    t = start
    prev = add(t, first, to, subject, wrap(first, FIRST[to[0]], opener), cc=cc, topic=topic, attach=attachment_for(topic, t))
    for _ in range(n - 1):
        t = t + timedelta(hours=rng.randrange(2, 70))
        t = WORKDAY(t).replace(hour=rng.randrange(8, 18), minute=rng.randrange(0, 60))
        sender = rng.choice([p for p in people if p != prev["frm"]])
        recips = [prev["frm"]] + [p for p in (prev["to"] + prev["cc"]) if p not in (sender, prev["frm"])][:2]
        to2 = [r for r in recips[:2]]
        cc2 = [r for r in recips[2:]]
        text = rng.choice(cfg["rep"]).format(thing=thing, day=day_phrase(t), tk=f"HL-{rng.randrange(100, 999)}",
                                              amt=f"{rng.randrange(2, 90) * 10} USD")
        prev = add(t, sender, to2, "Re: " + subject, wrap(sender, FIRST[to2[0]], text, prev), cc=cc2, parent=prev,
                   topic=topic, attach=attachment_for(topic, t) if rng.random() < 0.1 else [])


# ---------- generated threads ----------
for topic, cfg in T.items():
    a, b = datetime(*cfg["win"][0], tzinfo=PT), datetime(*cfg["win"][1], tzinfo=PT)
    specs = cfg["subj"][:]
    rng.shuffle(specs)
    for spec in specs:
        build_thread(topic, spec, when_in(a, b), jordan_chance=0.25)
# a second, shorter pass so busy topics have more than one thread per subject over two years
for topic in ("launch", "budget", "client"):
    cfg = T[topic]
    a, b = datetime(*cfg["win"][0], tzinfo=PT), datetime(*cfg["win"][1], tzinfo=PT)
    for spec in rng.sample(cfg["subj"], 5):
        s2 = (spec[0] + " (follow-up)", spec[1], "Following up on this topic with a few new details since the last round.")
        build_thread(topic, s2, when_in(a, b), jordan_chance=0.25)

# ---------- newsletters ----------
DW = ["Why constraints make better logos", "Ten color palettes from real harbors", "Type pairing without the guesswork",
      "Designing for glanceable screens", "What a good brief looks like", "The case for boring grids",
      "Motion that explains instead of decorates", "Photo direction for outdoor brands", "Accessible contrast in practice",
      "How small studios price fixed-scope work", "Sketching before pixels", "Icon sets that scale"]
CT = ["New: scheduled exports", "Five tips for faster builds", "Uptime report for the quarter", "Storage tiers explained",
      "Changelog: dark mode for the console", "Cost alerts you will actually read", "Release notes: API v3 preview",
      "Spring maintenance windows"]
for sender, heads, label in (("dw", DW, "Design Weekly"), ("ct", CT, "Cloud Toolbox Digest")):
    for i in range(14 if sender == "dw" else 12):
        d = datetime(2023, 1, 12, 7, 0, tzinfo=PT) + timedelta(days=int(i * 52 / (14 if sender == "dw" else 12) * 2 + rng.randrange(0, 4)))
        if d > datetime(2024, 12, 20, tzinfo=PT):
            continue
        head = heads[i % len(heads)]
        bullets = rng.sample(["A short interview with a studio founder", "Three links worth your Friday", "A tool we are trying this month",
                              "Reader question of the issue", "A free template pack", "What we are reading", "Poll results"], 3)
        text = f"{label} issue {i + 1}\n\n{head}\n\nIn this issue:\n" + "\n".join(f"- {b}" for b in bullets) + \
               f"\n\nRead online: https://news.example/{sender}/{i + 1}\nUnsubscribe: https://news.example/unsub/{sender}\n"
        html = f"<html><body><h1>{head}</h1><p>In this issue:</p><ul>" + "".join(f"<li>{b}</li>" for b in bullets) + \
               f"</ul><p><a href='https://news.example/{sender}/{i + 1}'>Read online</a> | <a href='https://news.example/unsub/{sender}'>Unsubscribe</a></p></body></html>"
        add(d, sender, ["dana"], f"{label} #{i + 1}: {head}", text, topic="newsletter", html=html,
            extra={"List-Unsubscribe": f"<https://news.example/unsub/{sender}>", "Precedence": "bulk"})

# ---------- misc company chatter ----------
MISC = [
    ("grace", "Studio holiday schedule", "We are closed {d}. Please set out-of-office messages and hand off anything urgent to Dana."),
    ("oscar", "Fire drill on {d}", "We will run a short fire drill around 11am on {d}. Meet at the harbor-side lot and check in with your floor warden."),
    ("tomas", "Planned network maintenance", "The office network will be down for about an hour on {d} after 6pm. Save your work and keep your laptop charged."),
    ("grace", "Shout-out: great client feedback", "A quick note to say Brightwave told me how pleased they are with the team's work this week. Well done everyone, truly."),
    ("naomi", "Benefits enrollment window", "Open enrollment for benefits runs through {d}. Forms are in the people folder; come to me with questions."),
    ("oscar", "Kitchen etiquette (again)", "Friendly reminder to label lunches and clear the fridge on Fridays. The mystery casserole has been retired."),
    ("chloe", "Team lunch on {d}", "Lunch is on the studio on {d}. Tell me your dietary needs by Wednesday so I can order for everyone."),
    ("tomas", "Password manager rollout", "We are moving everyone to the shared password manager this month. Invites go out on {d}; please set up two-factor sign-in."),
    ("dana", "Welcome our new starter", "Please give a warm welcome to our newest teammate who starts on {d}. Say hi when you see them in the studio."),
    ("grace", "All-hands recap", "Thanks for joining the all-hands. Slides are in the shared drive and the next one is on {d}."),
    ("oscar", "Parking lot resurfacing", "The lot behind the building is being resurfaced on {d}. Please use the street spots that day."),
    ("elena", "Reminder: submit time sheets", "Time sheets are due {d}. Please use the project codes from the finance folder."),
    ("samir", "Welcome back from the trade show", "The trade show was a success: 31 leads, six demos booked. Notes are in the CRM; please follow up this week."),
    ("hana", "Design crit this Thursday", "Open design crit on {d} at 3pm. Bring work in progress, the rougher the better."),
    ("priya", "Studio reading list", "Starting a shared reading list in the wiki. Add any books, articles or talks that changed how you work."),
    ("tomas", "Backup test results", "We restored last night's backup to a test machine and everything came back. Next test is on {d}."),
    ("grace", "Thank you for a strong year", "As the year wraps up I want to thank every one of you. We shipped a lot and learned even more."),
    ("naomi", "Performance review cycle: dates and forms", "The annual performance review cycle opens {d}. Self-assessments are due in two weeks and manager reviews follow. Forms are in the people folder."),
    ("oscar", "Bike storage now available", "We have room for eight bikes in the back hall. Sign the sheet on the kitchen door."),
    ("dana", "Operations update", "Quick operations update: the move is on track, the new vendor contracts are signed and the budget review is next week."),
]
for i, (frm, subj, body) in enumerate(MISC * 2):
    a = datetime(2023, 1, 9, tzinfo=PT)
    d = when_in(a, datetime(2024, 12, 15, tzinfo=PT))
    ds = (d + timedelta(days=rng.randrange(5, 25))).strftime("%b %d")
    to = [p for p in STAFF if p != frm]
    if i >= len(MISC) and rng.random() < 0.5:
        continue
    add(d, frm, ["dana"] if frm != "dana" else ["grace"], subj.format(d=ds), wrap(frm, "team", body.format(d=ds)),
        cc=rng.sample(to, 4), topic="misc")

# ---------- unrelated "performance" emails (app / sales / site) ----------
a = add(ts(2023, 5, 16, 10, 12), "ravi", ["tomas"], "Tidewatch app performance: cold start regression",
        "Hi Tomas,\n\nApp performance on older phones has regressed. Cold start went from 1.2 s to 2.9 s on the test device after the tide-table sync change. "
        "Profiling points at the database load on the main thread. I will move it to a background queue and re-measure.\n\nRavi", cc=["dana"], topic="perf")
b = add(ts(2023, 5, 16, 14, 40), "tomas", ["ravi"], "Re: Tidewatch app performance: cold start regression",
        "Good catch. Please also add a performance test to CI so we notice this before testers do. Target is under 1.5 s cold start on the oldest supported device.\n\nTomas",
        cc=["dana"], parent=a, topic="perf")
add(ts(2023, 5, 18, 9, 5), "ravi", ["tomas"], "Re: Tidewatch app performance: cold start regression",
    "Fix is merged. Cold start is back to 1.3 s and the new performance test is running in CI. Ticket HL-412 closed.\n\nRavi", cc=["dana"], parent=b, topic="perf")
a = add(ts(2023, 8, 2, 11, 30), "samir", ["grace", "dana"], "Sales performance: Q2 summary",
        "Hi both,\n\nSales performance for Q2: 14 new accounts, 3 renewals, pipeline up 22 percent against Q1. We missed the large-account target by one deal. "
        "Full numbers are in the dashboard; happy to walk through them.\n\nSamir", topic="perf")
add(ts(2023, 8, 2, 16, 2), "grace", ["samir"], "Re: Sales performance: Q2 summary",
    "Thanks Samir. Strong quarter overall. Let's talk about the large-account pipeline at the Thursday meeting.\n\nGrace", cc=["dana"], parent=a, topic="perf")
add(ts(2023, 10, 24, 10, 0), "tomas", ["dana", "chloe"], "Website performance audit results",
    "Hi,\n\nWebsite performance audit is done. The homepage scored 62 for load speed; the hero video and unoptimized images are the main cause. "
    "We can get to 90 with image compression and lazy loading, about two days of work.\n\nTomas", topic="perf")
add(ts(2024, 1, 17, 13, 15), "chloe", ["grace", "samir"], "Campaign performance report: holiday promotion",
    "Hi,\n\nCampaign performance for the holiday promotion: 48,000 impressions, 2.1 percent click-through and 96 trial starts. Email beat social by a wide margin. "
    "Recommendations are in the attached notes.\n\nChloe",
    topic="perf", attach=[txt_att("campaign-notes.txt", "Holiday promotion\nImpressions: 48000\nCTR: 2.1%\nTrial starts: 96\nBest channel: email")])
add(ts(2024, 4, 9, 9, 45), "samir", ["grace", "dana"], "Sales performance dashboard is live",
    "The new sales performance dashboard is live. It shows pipeline, win rate and average deal size by month. Please tell me what is missing.\n\nSamir", topic="perf")
a = add(ts(2024, 5, 7, 15, 20), "ravi", ["tomas"], "Slow search screen: database query performance",
        "The search screen takes four seconds on big libraries. Query performance is the problem: a missing index on the tide-station table. I added it and the screen now loads in 300 ms.\n\nRavi", topic="perf")
add(ts(2024, 5, 8, 8, 50), "tomas", ["ravi"], "Re: Slow search screen: database query performance",
    "Nice. Please write up what you found so we check for other missing indexes during the next release.\n\nTomas", parent=a, topic="perf")
add(ts(2024, 8, 6, 10, 10), "elena", ["dana", "grace"], "Project margin report: studio performance by client",
    "Hi,\n\nStudio performance by client for the first half: Brightwave margin is 34 percent, the app work 41 percent, small projects 28 percent. "
    "Details in the attached sheet.\n\nElena", topic="perf",
    attach=[csv_att("margins-h1-2024.csv", ["Client", "Revenue", "Margin"], [("Brightwave", 182000, "34%"), ("Tidewatch", 96000, "41%"), ("Small projects", 41000, "28%")])])
add(ts(2024, 9, 12, 11, 0), "ravi", ["tomas", "dana"], "Performance testing Tidewatch 2.1 on older phones",
    "Ran performance tests for 2.1 on three older phones. Scrolling stays smooth, but memory use grows 15 percent with the new trip-plan view. I will profile it this week.\n\nRavi", topic="perf")

# ---------- Jordan Avery storyline (workplace-generic) ----------
J = "jordan"
s = add(ts(2024, 2, 6, 9, 30), "marcus", ["dana"], "Q1 staffing check-in",
        "Hi Dana,\n\nQuick staffing check-in for Q1. Jordan has taken over day-to-day Brightwave coordination, and Jo is great with the client. "
        "My one concern is workload: the asset list and the review schedule are both owned by Jordan right now, and I want to keep a closer eye on how that goes.\n\nMarcus", topic="case")
n1 = add(ts(2024, 2, 20, 16, 0), "marcus", [J], "1:1 notes: Feb 20",
         "Hi Jordan,\n\nNotes from today's 1:1:\n\n- Priorities: Brightwave asset list (due Mar 1), review schedule, packaging proof tracking\n- Concern: two small deadlines slipped in January without a heads-up\n"
         "- Agreed: weekly 1:1, flag risks as soon as you see them\n- Your ask: clearer priorities when several things land at once\n\nMarcus", cc=["dana"], topic="case")
add(ts(2024, 3, 5, 10, 15), J, ["marcus"], "Re: 1:1 notes: Feb 20",
    "Hi Marcus,\n\nThanks for the notes. I am sorry about the asset list; the vendor sent images late. I will deliver it Friday and I will flag risks earlier from now on.\n\nJordan",
    parent=n1, topic="case")
n2 = add(ts(2024, 3, 8, 9, 0), "marcus", [J], "Asset list for Brightwave: now a week late",
         "Jordan,\n\nThe Brightwave asset list is now a week late and Lucia is waiting on it. Please send it today and tell me what is blocking you.\n\nMarcus", cc=["naomi"], topic="case")
add(ts(2024, 3, 8, 11, 40), J, ["marcus"], "Re: Asset list for Brightwave: now a week late",
    "Marcus,\n\nSending the asset list now (attached). The blocker was the packaging vendor, who changed file formats twice. I should have escalated sooner. Sorry for the delay.\n\nJordan",
    cc=["naomi"], parent=n2, topic="case",
    attach=[csv_att("brightwave-asset-list.csv", ["Asset", "Owner", "Status"], [("Logo pack", "Hana", "Ready"), ("Packaging dielines", "Jordan", "Ready"), ("Tag artwork", "Ben", "In review")])])
c1 = add(ts(2024, 3, 19, 14, 20), "marcus", ["naomi"], "Support for Jordan",
         "Hi Naomi,\n\nI want to talk about Jordan's performance. There is a pattern: three missed deadlines since January, each one communicated late. "
         "Jo does warm, thoughtful work when things are calm. I would like advice on how to set clear expectations and what support I can offer.\n\nMarcus", cc=["dana"], topic="case")
add(ts(2024, 3, 21, 9, 10), "naomi", ["marcus"], "Re: Support for Jordan",
    "Marcus,\n\nThanks for raising this early. Suggested approach: write the expectations down, check in weekly, keep notes of each conversation and ask Jo what would help. "
    "Let's meet next week and agree the wording.\n\nNaomi", cc=["dana"], parent=c1, topic="case")
add(ts(2024, 4, 2, 15, 30), "marcus", [J], "1:1 notes: April 2",
    "Hi Jordan,\n\nNotes from today:\n\n- Asset list delivered, thank you\n- Review deck v2 still open; new date is Apr 16\n- Packaging proofs: you will own the tracker\n- I offered to move one task to Ben; you preferred to keep it\n\nNext 1:1 on Apr 16.\n\nMarcus",
    topic="case")
add(ts(2024, 4, 2, 17, 5), "dana", ["marcus"], "Jo's workload",
    "Marcus,\n\nJo mentioned the schedule feels tight with the Brightwave review and the packaging proofs landing the same week. Can we move the review by a few days?\n\nDana", topic="case")
add(ts(2024, 4, 18, 11, 25), "marcus", ["priya"], "Brightwave review deck: draft v2 still outstanding",
    "Priya,\n\nFollowing up on yesterday: draft v2 of the review deck is still outstanding and the client call is Monday. Can you cover the missing slides if it does not land by tonight?\n\nMarcus",
    cc=[J], topic="case")
e1 = add(ts(2024, 5, 7, 10, 0), "marcus", [J], "Written expectations for May",
         "Jordan,\n\nFollowing our conversations, here are the expectations I would like us to work to through May:\n\n1. Deliverables are on time or flagged at least two days ahead\n"
         "2. The Brightwave tracker is updated every Friday\n3. Questions about priorities come to me the same day\n\nThe goal is to give you clarity, not pressure. Let's review on May 28.\n\nMarcus",
         cc=["naomi"], topic="case")
add(ts(2024, 5, 9, 9, 20), J, ["marcus"], "Re: Written expectations for May",
    "Marcus,\n\nThanks for putting this in writing, it helps. One question: when two clients need something on the same day, who decides which comes first? I will update the tracker every Friday starting this week.\n\nJordan",
    cc=["naomi"], parent=e1, topic="case")
add(ts(2024, 5, 30, 13, 45), "naomi", ["marcus"], "Documentation for Jordon's file",
    "Marcus,\n\nFor Jordon's file I have the Feb 20 and April 2 notes and the May expectations. Please send the May 28 review notes too, so the record is complete and consistent.\n\nNaomi",
    cc=["dana"], topic="case")
add(ts(2024, 6, 11, 16, 30), "marcus", ["dana"], "Launch week coverage",
    "Dana,\n\nCoverage for launch week is set. Jo handled all the vendor calls last week and handled them well, so I am comfortable leaving that with Jordan. Hana is the backup.\n\nMarcus", topic="case")
add(ts(2024, 6, 25, 7, 50), "jo_home", ["marcus"], "Out Thursday",
    "Hi Marcus,\n\nI am not feeling well and will be out Thursday. The tracker is up to date and Ben has the vendor contact if anything comes up. Writing from my personal email since I am not at my laptop.\n\nJo",
    cc=[J], topic="case")
n3 = add(ts(2024, 7, 9, 15, 0), "marcus", [J], "1:1 notes: July 9",
         "Hi Jordan,\n\nNotes from today:\n\n- Launch checklist: one item missed, the store screenshots\n- Tracker updated every Friday in June, thank you\n- Support: pairing with Hana on asset tracking for two weeks\n- Next steps: review again at the end of July\n\nMarcus",
         topic="case")
add(ts(2024, 7, 10, 9, 40), "marcus", ["hana"], "Pairing on asset tracking",
    "Hana,\n\nThanks for agreeing to pair on asset tracking for the next two weeks. Two sessions of 45 minutes should be enough. Looping in the owner of the tracker so you can set a time.\n\nMarcus",
    cc=[J], topic="case")
add(ts(2024, 7, 31, 14, 10), "marcus", ["naomi"], "Mid-year check on Jordan",
    "Naomi,\n\nMid-year view on Jordan: two deadlines hit, one missed, communication is improving but performance is still inconsistent. I think a structured improvement plan would help, with clear milestones.\n\nMarcus",
    cc=["dana"], topic="case")
p1 = add(ts(2024, 8, 14, 11, 0), "naomi", [J, "marcus"], "Improvement plan for Jordan: draft for discussion",
         "Hi Jordan, hi Marcus,\n\nAttached is a draft 60-day improvement plan. It lists three milestones, weekly check-ins and the support offered (pairing with Hana, a clearer priority list from Marcus). "
         "Please read it before we meet on Friday; nothing is final until we have talked.\n\nNaomi",
         topic="case", attach=[pdf_att("improvement-plan-draft.pdf", "60-day improvement plan (draft)", ["Milestone 1: tracker current every Friday", "Milestone 2: deliverables on time or flagged 2 days ahead", "Milestone 3: launch checklist owned end to end", "Check-ins: weekly with Marcus", "Support: pairing with Hana, priority list from Marcus"])])
add(ts(2024, 8, 15, 9, 30), J, ["naomi"], "Re: Improvement plan for Jordan: draft for discussion",
    "Hi Naomi,\n\nThank you for the draft. The milestones are clear and fair. Two questions: can milestone 2 allow for client-driven changes, and who signs off on the milestones at the end? Happy to discuss Friday.\n\nJordan",
    cc=["marcus"], parent=p1, topic="case")
add(ts(2024, 8, 28, 15, 45), "marcus", [J], "1:1 notes: Aug 28 (plan week 2)",
    "Hi Jordan,\n\nNotes from today:\n\n- Milestone 1 on track: tracker current three weeks running\n- Milestone 2: one slip, flagged early, accepted as within the plan\n- Pairing with Hana helped; two more sessions\n\nKeep going.\n\nMarcus", topic="case")
ck = add(ts(2024, 9, 18, 14, 0), "marcus", [J], "Plan checkpoint: 30 days",
         "Jordan,\n\nCheckpoint at the 30 day mark: all three milestones are on track. The launch checklist was completed end to end without reminders. Let's keep the same rhythm for the second half.\n\nMarcus",
         cc=["naomi"], topic="case")
add(ts(2024, 10, 9, 10, 35), "marcus", ["dana"], "Jo's progress",
    "Dana,\n\nSharing good news: Jo delivered the Q4 asset schedule a week early and the client noticed. Performance on the plan is solid, and the team likes working with Jordan.\n\nMarcus",
    cc=["naomi"], topic="case")
add(ts(2024, 10, 23, 12, 20), J, ["marcus"], "Thanks, and a question about the Q4 roadmap",
    "Hi Marcus,\n\nThank you for the feedback in our last 1:1. I would like to take on a bigger part of the Q4 roadmap if there is room. Could we talk about what that would look like?\n\nJordan",
    topic="case")
add(ts(2024, 11, 20, 9, 0), "naomi", [J], "Improvement plan closed",
    "Hi Jordan,\n\nThe 60-day plan is complete and all milestones were met, so we are closing it. Congratulations, Jordan, and thank you for the effort. Marcus and Dana are copied; the file will note the plan was completed successfully.\n\nNaomi",
    cc=["marcus", "dana"], topic="case")
add(ts(2024, 11, 21, 8, 40), "dana", ["marcus"], "Great news about Jo",
    "Marcus,\n\nI saw Naomi's note. Great news about Jo, and credit to you for the patient coaching. Let's make sure it shows in the year-end recognition.\n\nDana", topic="case")

# ---------- calendar invites ----------
A = lambda *k: list(k)
invite(ts(2023, 2, 27, 9), "chloe", A("priya", "tomas", "ravi", "hana", "dana"), "Tidewatch 2.0 kickoff", ts(2023, 3, 6, 10), 1.5, "Studio, big table", "Kickoff for the Tidewatch 2.0 release: scope, owners and timeline.")
invite(ts(2023, 4, 10, 9), "naomi", A("marcus", "priya", "tomas"), "Candidate panel interview", ts(2023, 4, 18, 14), 1.5, "Meeting room 2", "Panel interview for the Senior Designer role.", mode="attach")
invite(ts(2023, 6, 12, 9), "elena", A("dana", "grace", "samir"), "Q2 budget review", ts(2023, 6, 20, 11), 1, "Video call", "Review of Q2 actuals against budget.")
invite(ts(2023, 7, 24, 9), "oscar", A("dana", "grace", "tomas"), "Pier 9 walkthrough", ts(2023, 8, 3, 15), 1, "Pier 9 Warehouse, Unit 3", "Walkthrough of the new unit with the property manager.", mode="attach")
invite(ts(2023, 9, 1, 9), "chloe", A("priya", "tomas", "ravi", "dana", "grace"), "Launch readiness review", ts(2023, 9, 12, 13), 1, "Studio, big table", "Go or no-go for the Tidewatch 2.0 release.")
invite(ts(2023, 11, 6, 9), "lucia", A("priya", "hana", "ben", "marcus"), "Brightwave brand review", ts(2023, 11, 14, 10), 1.5, "Video call", "Brand review with Brightwave Outdoor. Link in the description.")
invite(ts(2023, 11, 3, 9), "oscar", A("dana", "grace", "tomas", "hana", "priya"), "Office move day", ts(2023, 11, 18, 0), 0, "Pier 9 Warehouse, Unit 3", "Moving day. Details in the move schedule.", allday=True)
invite(ts(2023, 12, 1, 9), "grace", STAFF[:], "Year-end all-hands", ts(2023, 12, 14, 16), 1, "Studio floor", "Year-end all-hands with snacks.")
invite(ts(2023, 12, 4, 9), "oscar", STAFF[:], "Holiday party", ts(2023, 12, 20, 0), 0, "The Boathouse Cafe", "Studio holiday party. Partners welcome.", allday=True)
invite(ts(2024, 2, 20, 12), "marcus", A(J), "1:1: Marcus and Jordan", ts(2024, 2, 27, 15), 0.5, "Meeting room 1", "Weekly check-in.", rrule="FREQ=WEEKLY;COUNT=20", mode="attach")
invite(ts(2024, 5, 10, 9), "lucia", A("priya", "hana", "callum", "marcus"), "Brightwave final presentation", ts(2024, 5, 23, 11), 1.5, "Video call", "Final presentation of the rebranded assets.")
invite(ts(2024, 9, 4, 9), "naomi", A("marcus", J), "Plan checkpoint: 30 days", ts(2024, 9, 18, 14), 0.5, "Meeting room 1", "30 day improvement plan checkpoint.")
invite(ts(2024, 12, 2, 9), "elena", A("dana", "grace"), "Year-end finance close", ts(2024, 12, 10, 10), 1, "Video call", "Walkthrough of the year-end close checklist.")
cancel = invite(ts(2024, 3, 18, 9), "dana", A("grace", "priya", "samir"), "Q3 planning workshop", ts(2024, 7, 9, 9), 3, "Studio, big table", "Planning workshop for Q3.", method="CANCEL", status="CANCELLED")
invite(ts(2024, 12, 12, 9), "grace", STAFF[:], "Long-range planning retreat", ts(2030, 9, 20, 9), 8, "The Boathouse Cafe", "Five-year planning retreat. Save the date.")
invite(ts(2024, 12, 12, 9, 5), "grace", STAFF[:], "10-year anniversary open house", ts(2031, 6, 14, 17), 3, "Pier 9 Warehouse, Unit 3", "Open house for clients and friends.")

# ---------- misc extras: a few bcc / forwards ----------
add(ts(2023, 10, 5, 9, 15), "dana", ["lucia"], "Notes from the Brightwave call", wrap("dana", "Lucia", "Notes from this morning's call are below. Callum wants the first logo round by the end of October. Copying Grace quietly so she has the context."),
    bcc=["grace"], topic="client")
add(ts(2024, 2, 14, 10, 0), "dana", ["oscar", "tomas", "elena"], "Quarterly all-hands agenda", wrap("dana", "all", "Agenda draft: 1) finance snapshot 2) launch retrospective 3) hiring plan 4) open questions. Reply with anything you want added."),
    bcc=["grace", "naomi"], topic="misc")

# ---------- deliberate duplicates (same body re-filed with a new or no Message-ID) ----------
base = [m for m in MSGS if m["topic"] in ("budget", "launch", "move", "misc") and not m["irt"] and not m["invite"]]
for k, m in enumerate(rng.sample(base, 12)):
    copy = dict(m, mid=None if k % 3 == 0 else mid(), refs=[], irt=None, attach=list(m["attach"]), box=None, dup_of=m)
    if k % 3 != 0:  # strategy: new Message-ID, same sender + subject + body
        copy["when"] = m["when"] + timedelta(minutes=rng.randrange(5, 600))
    MSGS.append(copy)

# ---------- mailbox routing & output ----------
CUT = datetime(2023, 7, 1, tzinfo=PT)
END = datetime(2024, 12, 31, 23, tzinfo=PT)
MSGS[:] = [m for m in MSGS if m["when"] <= END]
for m in MSGS:
    if m["box"] or "dup_of" in m:
        continue
    if m["frm"] == "dana":
        m["box"] = "Sent"
    elif m["when"] < CUT:
        m["box"] = "Archive"
    elif m["topic"] in ("launch", "client", "case", "perf"):
        m["box"] = "Projects"
    else:
        m["box"] = "Inbox"
for m in MSGS:  # a duplicate must live in a different mailbox than its original
    if "dup_of" in m:
        m["box"] = "Archive" if m["dup_of"]["box"] != "Archive" else "Projects"


def addr(k):
    n, a, _ = P[k]
    return formataddr((n, a))


def build(m):
    random.seed(m["mid"] or m["subject"] + str(m["when"]))  # MIME boundaries use the global RNG
    msg = EmailMessage()
    msg["From"] = addr(m["frm"])
    msg["To"] = ", ".join(addr(k) for k in m["to"])
    if m["cc"]:
        msg["Cc"] = ", ".join(addr(k) for k in m["cc"])
    if m["bcc"]:
        msg["Bcc"] = ", ".join(addr(k) for k in m["bcc"])
    msg["Subject"] = m["subject"]
    msg["Date"] = format_datetime(m["when"])
    if m["mid"]:
        msg["Message-ID"] = f"<{m['mid']}>"
    if m["irt"]:
        msg["In-Reply-To"] = f"<{m['irt']}>"
        msg["References"] = " ".join(f"<{r}>" for r in m["refs"])
    for k, v in m["extra"].items():
        msg[k] = v
    msg.set_content(m["body"])
    if m["html"]:
        msg.add_alternative(m["html"], subtype="html")
    if m["invite"]:
        body, mode, method = m["invite"]
        if mode == "attach":
            msg.add_attachment(body, subtype="calendar", filename="invite.ics")
        else:
            msg.add_attachment(body, subtype="calendar", params={"method": method}, disposition="inline")
    for name, ctype, data in m["attach"]:
        main, sub = ctype.split("/")
        if isinstance(data, bytes):
            msg.add_attachment(data, maintype=main, subtype=sub, filename=name)
        else:
            msg.add_attachment(data, subtype=sub, filename=name)
    return msg.as_bytes()


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else sys.exit(__doc__)
    out.mkdir(parents=True, exist_ok=True)
    for box in MAILBOXES:
        rows = sorted((m for m in MSGS if m["box"] == box), key=lambda m: m["when"])
        with open(out / f"{box}.mbox", "wb") as f:
            for m in rows:
                raw = re.sub(rb"(?m)^From ", b">From ", build(m))
                f.write(b"From %s %s\n" % (P[m["frm"]][1].encode(), m["when"].astimezone(UTC).strftime("%a %b %e %H:%M:%S %Y").encode()))
                f.write(raw.rstrip(b"\n") + b"\n\n")
        print(f"{box}.mbox: {len(rows)} messages")
    print(f"total: {len(MSGS)}")


if __name__ == "__main__":
    main()
