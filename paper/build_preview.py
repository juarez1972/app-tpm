#!/usr/bin/env python3
"""Faithful IEEE-style two-column PDF PREVIEW of hybrid_zt_nia.tex.
This is a visual-QA preview only; the authoritative deliverable is the .tex.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, FrameBreak, NextPageTemplate,
                                CondPageBreak)

FD = "/usr/share/fonts/truetype/liberation"
pdfmetrics.registerFont(TTFont("Serif", f"{FD}/LiberationSerif-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Serif-B", f"{FD}/LiberationSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Serif-I", f"{FD}/LiberationSerif-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Serif-BI", f"{FD}/LiberationSerif-BoldItalic.ttf"))
pdfmetrics.registerFont(TTFont("Mono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-B",
                              italic="Serif-I", boldItalic="Serif-BI")

OUT = "/home/user/workspace/app-tpm/paper/hybrid_zt_nia_preview.pdf"
PAGE = letter
LM = RM = 0.6*inch
TM = 0.7*inch
BM = 0.7*inch
GUT = 0.25*inch
colw = (PAGE[0]-LM-RM-GUT)/2

styles = getSampleStyleSheet()
def S(name, **kw):
    base = dict(fontName="Serif", fontSize=9, leading=10.6, alignment=TA_JUSTIFY)
    base.update(kw); return ParagraphStyle(name, **base)

body = S("body", firstLineIndent=10)
body0 = S("body0")
h1 = S("h1", fontName="Serif-B", fontSize=9.5, leading=12, spaceBefore=8, spaceAfter=3,
        alignment=TA_CENTER)
h2 = S("h2", fontName="Serif-BI", fontSize=9, leading=11, spaceBefore=5, spaceAfter=2,
       alignment=TA_LEFT)
abst = S("abst", fontName="Serif-B", fontSize=8.5, leading=10.2)
absbody = S("absbody", fontSize=8.5, leading=10.2, fontName="Serif")
kw = S("kw", fontSize=8.5, leading=10.2)
caption = S("caption", fontSize=7.6, leading=9, alignment=TA_CENTER, fontName="Serif")
cell = S("cell", fontSize=7, leading=8.2, alignment=TA_LEFT, firstLineIndent=0)
cellb = S("cellb", fontSize=7, leading=8.2, alignment=TA_LEFT, fontName="Serif-B", firstLineIndent=0)
code = S("code", fontName="Mono", fontSize=6.6, leading=8, alignment=TA_LEFT, firstLineIndent=0,
         backColor=colors.HexColor("#F4F4F2"), borderPadding=3)

title = S("title", fontName="Serif-B", fontSize=15, leading=18, alignment=TA_CENTER)
authors = S("authors", fontSize=10, leading=13, alignment=TA_CENTER)
foot = S("foot", fontSize=7, leading=8.4, alignment=TA_LEFT)

def mk(text, st=body): return Paragraph(text, st)

# ---- flowables ----
story = []

def section(num, name):
    story.append(Paragraph(f"{num}.&nbsp;&nbsp;{name.upper()}", h1))
def sub(name):
    story.append(Paragraph(f"<i>{name}</i>", h2))
def para(t): story.append(Paragraph(t, body))
def para0(t): story.append(Paragraph(t, body0))

def tbl(caption_txt, header, rows, colWidths, label, span_note=None, full=False):
    els=[]
    els.append(Paragraph(f"<b>{label}</b><br/>{caption_txt}", caption))
    els.append(Spacer(1,2))
    data=[[Paragraph(f"<b>{h}</b>", cell) for h in header]]
    for r in rows:
        data.append([Paragraph(c, cell) for c in r])
    t=Table(data, colWidths=colWidths, repeatRows=1)
    ts=[('FONT',(0,0),(-1,-1),'Serif',7),
        ('LINEABOVE',(0,0),(-1,0),0.8,colors.black),
        ('LINEBELOW',(0,0),(-1,0),0.5,colors.black),
        ('LINEBELOW',(0,-1),(-1,-1),0.8,colors.black),
        ('TOPPADDING',(0,0),(-1,-1),1.5),('BOTTOMPADDING',(0,0),(-1,-1),1.5),
        ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
        ('VALIGN',(0,0),(-1,-1),'TOP')]
    t.setStyle(TableStyle(ts))
    els.append(t)
    if span_note:
        els.append(Paragraph(span_note, S("note", fontSize=6.6, leading=8)))
    els.append(Spacer(1,6))
    return els

# ============ FRONT MATTER (spans full width via first frame) ============
story.append(Paragraph("A Hybrid Zero Trust Architecture for Non-Interactive "
    "Authentication: Integrating Hardware Trust Anchors with Software-Defined "
    "Secret Management in Infrastructure as Code", title))
story.append(Spacer(1,6))
story.append(Paragraph("Juliano S. Langaro, Altair O. Santin, Eduardo K. Viegas, "
    "Fellipe M. Veiga, and Juarez Oliveira", authors))
story.append(Paragraph("<font size=8><i>Graduate Program in Computer Science (PPGIa), "
    "PUCPR, Curitiba, Brazil</i></font>", S("aff", fontSize=8, alignment=TA_CENTER, leading=10)))
story.append(Spacer(1,8))

ABSTRACT = ("Non-Interactive Authentication (nIA)&mdash;the machine-to-machine "
"authentication that underpins Infrastructure as Code (IaC) pipelines and "
"unattended IoT fleets&mdash;is chronically undermined by the <i>Secret Zero</i> "
"problem: a long-lived credential must be planted in software to bootstrap every "
"other secret, and that credential is extractable under OS compromise (MITRE "
"ATT&amp;CK T1003). This paper presents a hybrid Zero Trust architecture that "
"anchors secret management in hardware trust anchors (TPM 2.0, with an upgrade "
"path to Intel SGX and TDX), delegates HashiCorp Vault auto-unseal to a physical "
"TPM, and confines every credential inside an identity-based network perimeter "
"(ZTNA) so intercepted secrets cannot be replayed outside their network context. "
"We describe a publicly released reference implementation whose IoT agent seals a "
"per-device one-time-password seed inside the device TPM while registering the "
"same seed in the server's Vault, so the plaintext seed never touches disk on "
"either side. We evaluate the design along three axes new to this revision: "
"(i) provisioning time for the full infrastructure, (ii) secret-retrieval latency "
"on the hot path, and (iii) resistance to an on-premises LLM red-team mapped to "
"MITRE ATT&amp;CK. We further contribute a proposed security-test suite that turns "
"the ad-hoc red-team into a repeatable regression gate executed after each "
"<font name=Mono size=7>terraform apply</font>. Measured software-path costs are "
"sub-25 microseconds; the hardware path adds a bounded, single-digit-to-tens-of-"
"milliseconds overhead while reducing Vault RTO from minutes to milliseconds. "
"Results are indicative estimates backed by prototype measurements; production-"
"scale empirical validation remains future work.")
story.append(Paragraph("<b><i>Abstract</i></b>&mdash;" + ABSTRACT, absbody))
story.append(Spacer(1,4))
story.append(Paragraph("<b><i>Index Terms</i></b>&mdash;Zero Trust, Trusted Platform "
"Module, HashiCorp Vault, non-interactive authentication, Infrastructure as Code, "
"MITRE ATT&amp;CK, IoT security, confidential computing, TOTP, LLM red-teaming.", kw))
story.append(Spacer(1,8))
story.append(FrameBreak())  # move into two-column body

# ============ BODY (two columns) ============
section("I", "Introduction")
para("<b>M</b>ODERN infrastructure is provisioned by code and operated by machines. "
"IaC engines apply changes without a human at the keyboard, and IoT fleets "
"authenticate at boot with no operator present. This non-interactive setting "
"removes the human factor that interactive MFA relies on and forces a bootstrap "
"credential&mdash;the Secret Zero&mdash;to live in software. Once an adversary attains "
"OS privileges, that credential and any secret it unlocks become extractable "
"(T1003 OS Credential Dumping; T1552 Unsecured Credentials).")
para("Software-only secret managers such as HashiCorp Vault mitigate sprawl but do "
"not by themselves solve Secret Zero: Vault must itself be unsealed, and the unseal "
"material is the new Secret Zero. Prior work by Oliveira <i>et al.</i> [12] showed "
"that a non-interactive OTP method materially raises the cost of Vault credential "
"abuse; this paper generalizes and hardens that line of work by moving the trust "
"anchor into silicon and enclosing the entire flow in an identity-based network "
"perimeter.")
para0("<b>Contributions.</b> This revision consolidates and extends our earlier "
"results: (1) a three-layer hybrid ZT design combining a hardware root of trust "
"(TPM 2.0, with SGX/TDX tiers), software-defined secret management (Vault "
"auto-unseal), and identity-based network access (ZTNA via an on-premises Twingate "
"connector); (2) a hardware-anchored OTP scheme in which the shared seed is sealed "
"inside the TPM and is non-exportable; (3) a protocol-agnostic two-channel MFA "
"model for unattended IoT over REST/HTTPS and MQTT/TLS; (4) an IaC-driven tiered "
"protection model (TPM/SGX/TDX) selected via Terraform sensitivity labels; "
"(5) a reproducible on-premises LLM adversary simulation mapped to MITRE ATT&amp;CK; "
"and&mdash;new&mdash;(6) a provisioning-time and secret-retrieval-latency "
"characterization of the running prototype, plus (7) a proposed security-test suite "
"that converts the red-team into a post-deployment regression gate.")

section("II", "Threat Model")
para0("We assume a root-level software adversary: an attacker with privileged code "
"execution on a host who cannot physically decap or glitch the TPM silicon. The "
"adversary's goals and MITRE ATT&amp;CK techniques are: credential extraction "
"(T1003, T1552); network interception (T1040 Network Sniffing); replay/token reuse "
"(T1550, T1078); privilege escalation (T1068, TA0004); and lateral movement "
"(T1021, TA0008). Physical TPM attacks (cold-boot, bus probing, decapping) are out "
"of scope; we rely on certified TPM 2.0 tamper-resistance [13] and note the residual "
"risk in Section VII.")
story.extend(tbl("Positioning Against Closely Related Work",
    ["Approach","HW anchor","Vault/secret","ZT net"],
    [["Perimeter VPN","no","partial","no"],
     ["Vault-only (software)","no","yes","no"],
     ["Oliveira <i>et al.</i> [12]","partial (OTP)","yes (OTP-hard.)","no"],
     ["LLM pen-testing [1,2,8]","n/a","n/a","n/a"],
     ["<b>This work</b>","<b>yes TPM/SGX/TDX</b>","<b>yes (auto-unseal)</b>","<b>yes</b>"]],
    [colw*0.30,colw*0.24,colw*0.28,colw*0.18], "TABLE I"))

section("III", "Architecture")
para("The architecture rests on the premise that software-only security is "
"insufficient for nIA. It is organized in three enforcement layers, each "
"corresponding to a concrete module in the public repository.")
sub("A. Layer 1 — Hardware Root of Trust (TPM/SGX/TDX)")
para0("Keys are generated inside the TPM with <font name=Mono size=7>fixedtpm</font> "
"and <font name=Mono size=7>fixedparent</font> so they never leave the silicon, even "
"under full OS compromise. Sealing binds material to PCR 0 and 7, so tampered "
"firmware or a disabled Secure Boot state prevents unsealing. Higher tiers use Intel "
"SGX (Gramine) and Intel TDX for CPU-encrypted memory, assigned automatically by IaC.")
sub("B. Layer 2 — Software-Defined Secret Management (Vault)")
para0("Vault is initialized (<font name=Mono size=7>sys/init</font>, five Shamir "
"shares, threshold three [11]) on first boot; unseal shares and root token are sealed "
"under a persistent TPM Storage Root Key. On every boot an initializer unseals the "
"shares from the TPM and applies them via the Vault REST API "
"(<font name=Mono size=7>sys/unseal</font>) with exponential backoff. No plaintext "
"secret and no <font name=Mono size=7>vault</font> binary are needed in the container; "
"no cloud KMS is involved. This eliminates Secret Zero for the secret manager and "
"collapses RTO from a manual multi-minute unseal to sub-second.")
sub("C. Layer 3 — Identity-Based Network Access (ZTNA)")
para0("A Twingate connector runs on-premises as a Docker container making only "
"<i>outbound</i> connections to the Twingate relay, so no inbound port is opened on "
"production. Vault and the IoT server are published as Twingate Resources reachable "
"only by identities satisfying an access policy (MFA, optional device posture). Even "
"a leaked OTP cannot be used outside the ZTNA network context, neutralizing lateral "
"movement (T1021).")
sub("D. Deployment Topology")
para0("Two virtual servers: <b>PPGIA96</b> (production) hosts Vault "
"(<font name=Mono size=7>:8200</font>), the IoT server (REST "
"<font name=Mono size=7>:5000</font> / MQTT <font name=Mono size=7>:8883</font>), and "
"the Twingate connector. <b>PPGIA95</b> (testing) hosts the security-testing module "
"and validation client, reaching PPGIA96 exclusively through Twingate. Production "
"exposes no inbound ports, so the only path in is an authorized, policy-checked ZTNA "
"session.")

section("IV", "Implementation")
para0("The prototype uses Docker Compose for orchestration, "
"<font name=Mono size=7>tpm2-tools</font>/<font name=Mono size=7>tpm2-pytss</font> for "
"TPM operations, and Python agents, on Ubuntu 22.04 LTS with physical "
"(Infineon SLB9670/9665) and virtual (<font name=Mono size=7>swtpm</font>) TPMs.")
sub("A. Hardware-Anchored One-Time Passwords")
para0("The hardware path computes a counter-based OTP whose HMAC is evaluated inside "
"the TPM (RFC 4226): HOTP(K,C) = Truncate(HMAC-SHA1<sub>TPM</sub>(K,C)), where K is a "
"non-exportable keyed-hash object in TPM NVRAM and C is a hardware monotonic counter, "
"so rollback is physically prevented.")
story.append(Paragraph("from tpm2_pytss import ESAPI<br/>"
"def generate_hardware_hotp(nv_index, key_handle):<br/>"
"&nbsp;&nbsp;&nbsp;&nbsp;ctx = ESAPI()<br/>"
"&nbsp;&nbsp;&nbsp;&nbsp;ctx.nv_increment(nv_index)&nbsp;&nbsp;# monotonic counter<br/>"
"&nbsp;&nbsp;&nbsp;&nbsp;counter = ctx.nv_read(nv_index)<br/>"
"&nbsp;&nbsp;&nbsp;&nbsp;mac = ctx.hmac(key_handle, counter)<br/>"
"&nbsp;&nbsp;&nbsp;&nbsp;return truncate_to_hotp(mac)&nbsp;# key stays in silicon", code))
story.append(Paragraph("Listing 1.&nbsp; HMAC delegated to the TPM; the key never "
"leaves the chip.", caption))
story.append(Spacer(1,4))
sub("B. Reference IoT Flow: TOTP Seed Sealed in the TPM")
para0("For full reproducibility on commodity hardware, the released IoT agent "
"implements a time-based OTP (TOTP, RFC 6238) as the functional analog of the HOTP "
"above; the TPM-delegated HMAC of Listing 1 is retained for hardware deployments and "
"is the intended production path. The released flow is protocol-agnostic (identical "
"for REST and MQTT):")
para0("<b>1) Provisioning</b> (once per device, "
"<font name=Mono size=7>init_device.sh</font>): a random Base32 TOTP seed is generated "
"in RAM, <i>sealed in the device TPM</i> under the persistent SRK "
"(<font name=Mono size=7>0x81010001</font>), and <i>registered in the server Vault</i> "
"at <font name=Mono size=7>secret/data/tpm-verified/iot/devices/&lt;id&gt;</font> "
"(field <font name=Mono size=7>otp_secret</font>). The plaintext seed never touches "
"disk. <b>2) Client boot</b>: verify TPM "
"(<font name=Mono size=7>tpm2_getrandom</font>) and unseal the seed into memory; a "
"changed PCR/boot state fails the unseal. <b>3) Authenticate</b>: send "
"<font name=Mono size=7>device_id</font> + current TOTP (REST "
"<font name=Mono size=7>POST /verify</font> or MQTT "
"<font name=Mono size=7>iot/verify</font>). <b>4) Server</b>: read the same seed from "
"Vault, cache it, and validate with &plusmn;1-window tolerance.")
para0("This asymmetry is the key property: the client holds its seed only inside "
"hardware (never on disk), while the server holds seeds only inside Vault (never in "
"code), so neither endpoint stores a reusable plaintext credential at rest.")
sub("C. IaC-Driven Tiered Protection")
para0("Terraform sensitivity labels map workloads to tiers (Table II): "
"<font name=Mono size=7>standard</font>&rarr;TPM 2.0; "
"<font name=Mono size=7>high</font>&rarr;TPM+SGX (Gramine); "
"<font name=Mono size=7>critical</font>&rarr;vTPM+TDX. Twingate resources and access "
"groups are themselves declared in Terraform, so the perimeter is version-controlled "
"alongside the compute tier.")
story.extend(tbl("Hybrid Server Protection Tiers (IaC-selected)",
    ["Label","HW anchor","TEE","Auto-unseal binding"],
    [["standard","TPM 2.0","none","PCR sealing"],
     ["high","TPM + SGX","Gramine LibOS","SGX + TPM"],
     ["critical","vTPM + TDX","TDX Trust Dom.","vTPM PCR"]],
    [colw*0.22,colw*0.24,colw*0.28,colw*0.26], "TABLE II"))

section("V", "Proposed Security-Test Suite")
para0("A recurring weakness of nIA deployments is that security is validated once, by "
"hand, and then drifts. We propose a repeatable suite run after every "
"<font name=Mono size=7>terraform apply</font> that gates promotion to production. "
"Family A is automated network/vuln testing driven by the "
"<font name=Mono size=7>pentest/</font> module; Family B checks functional security "
"invariants of the TPM+Vault+ZTNA flow (Table III). Because Family A LLM agents run "
"fully on-premises (<font name=Mono size=7>pentestv3.py</font>), no architectural "
"detail leaves the environment&mdash;a prerequisite for a federal-court network.")

section("VI", "Evaluation")
para0("<b>Scope disclaimer.</b> Results combine software simulation "
"(<font name=Mono size=7>swtpm</font>, Ollama), prototype measurements on a controlled "
"testbed, and analytical estimation&mdash;indicative estimates, not confirmed "
"production benchmarks. Directly measured values are marked <b>(m)</b>; analytically "
"estimated values <b>(e)</b>.")
sub("A. Automated Adversary Simulation via Local LLM Agents")
para0("Following autonomous pen-testing frameworks [1,2,8], we drive a local LLM "
"adversary (Llama 3.1 via Ollama) with two tools "
"(<font name=Mono size=7>http_request</font>, "
"<font name=Mono size=7>encode_payload</font>), a 5&ndash;10 turn limit, and n=100 "
"independent runs per technique. Against the hybrid architecture the observed bypass "
"rate is 0% across five techniques (5&times;100 = 500 runs total), 95% Wilson upper "
"bound 3.6% per technique; the software-only baseline averages 18.4% (Table IV).")
para0("Two threat-model techniques&mdash;T1040 (sniffing) and T1550 (replay)&mdash;are "
"addressed by TLS transport and by invariants B2/B3/B7 of Table III rather than by the "
"LLM agent, reconciling the threat model with the simulated techniques.")
sub("B. IoT Prototype and TPM Conformance")
para0("Table V reports IoT results on Raspberry Pi and under "
"<font name=Mono size=7>swtpm</font>; TPM conformance (SHA-256, HMAC, NV counters, PCR "
"ops) was validated with ELTT2.")
sub("C. Provisioning Time of the Full Infrastructure (new)")
para0("We characterize the time to bring the PPGIA96 stack from bare Docker to a "
"healthy, unsealed state: the <font name=Mono size=7>vault-tpm</font> services "
"(<font name=Mono size=7>vault:1.13.3</font> plus initializer and TPM-validator "
"builds), the IoT server (REST build, or Mosquitto + MQTT build), and the Twingate "
"connector. Table VI decomposes the budget. TPM auto-unseal is the decisive win: it "
"removes the manual multi-minute unseal from the critical path, reducing Vault RTO to "
"sub-second (Table VIII).")
sub("D. Secret-Retrieval Latency on the Hot Path (new)")
para0("The server obtains a seed via the cache&rarr;Vault KV v2&rarr;"
"<font name=Mono size=7>.env</font> fallback chain of "
"<font name=Mono size=7>load_device_secret</font>. We measured the software "
"components directly (20,000 iterations) and estimate the cold Vault round-trip from "
"typical <font name=Mono size=7>hvac</font> KV v2 LAN latency (Table VII). The "
"dominant cost is one cold Vault read per device; every subsequent retrieval is a warm "
"cache hit at sub-microsecond cost.")
sub("E. Performance Overhead by Protection Tier")
para0("Table VIII places these measurements in end-to-end context across the four "
"tiers. The hybrid design adds ~75&ndash;105 ms end-to-end while collapsing Vault RTO "
"by ~99.8%.")

# in-column narrow tables V, VI, VII
story.extend(tbl("IoT Prototype Test Results",
    ["Test case","Platform","TPM","Result"],
    [["Boot-time unseal","RPi 4","SLB9670","OK; ~280 ms (e)"],
     ["TOTP/HOTP under load","RPi 5","swtpm","OK; ~68 ms avg (e)"],
     ["PCR enforcement","ARM64","fTPM","Tampered boot blocked (m)"],
     ["Counter rollback","all","phys.+virt.","0 / 10,000 rollbacks (m)"],
     ["Offline sealed cred","RPi 4","SLB9670","24 h TTL enforced (e)"]],
    [colw*0.32,colw*0.18,colw*0.20,colw*0.30], "TABLE V"))
story.extend(tbl("Provisioning Budget for the PPGIA96 Production Stack",
    ["Phase","Cold (first run)","Warm (cached)"],
    [["Image pull + local builds","~3&ndash;6 min (e)","0 s (cached)"],
     ["Container start to healthy","~15&ndash;30 s (e)","~15&ndash;30 s (e)"],
     ["Vault sys/init (5/3 shares)","~1&ndash;2 s (e)","&mdash; (init.)"],
     ["TPM seal shares + token","~12.2 ms/obj (m)","&mdash;"],
     ["TPM auto-unseal (RTO)","~300 ms (e)","~300 ms (e)"],
     ["ZTNA connector register","~2&ndash;5 s (e)","~2&ndash;5 s (e)"],
     ["<b>Total to production</b>","<b>~3.5&ndash;6.5 min (e)</b>","<b>~25&ndash;45 s (e)</b>"]],
    [colw*0.44,colw*0.29,colw*0.27], "TABLE VI"))
story.extend(tbl("Secret-Retrieval and OTP Latency (software path, 20,000 iters)",
    ["Operation","Mean","p95","Source"],
    [["TOTP generation (client)","0.009 ms","0.009 ms","(m) pyotp .now()"],
     ["TOTP verification (server)","0.018 ms","0.019 ms","(m) pyotp .verify"],
     ["Seed read — warm (cache)","0.0002 ms","0.0003 ms","(m) in-proc cache"],
     ["Seed read — cold (Vault KV)","~8&ndash;12 ms","~15 ms","(e) hvac KV v2 LAN"],
     ["TPM health check","6.98 ms","7.98 ms","(m) tpm2_getrandom"],
     ["TPM seed provisioning (once)","12.22 ms","&mdash;","(m) createprimary+seal"]],
    [colw*0.36,colw*0.15,colw*0.15,colw*0.34], "TABLE VII"))

section("VII", "Discussion")
sub("A. Limitations of the LLM Red-Team")
para0("The LLM adversary gives reproducible, MITRE-mapped regression testing, but "
"(i) depends on prompt quality and a two-tool set; (ii) the turn limit constrains "
"multi-step chains; (iii) 0% at n=100 carries a 95% Wilson upper bound of 3.6%, not "
"absolute zero; (iv) it augments rather than replaces human red-teams.")
sub("B. Two-Channel MFA for IoT")
para0("Devices combine a TPM-bound identity (Channel 1, non-cloneable) with an "
"out-of-band approval (Channel 2), both within a 30 s window aligned to the RFC 6238 "
"time-step. An attacker must defeat the TPM (physically infeasible without silicon "
"tampering [6]) and compromise the operator's out-of-band channel.")
sub("C. An Additional Point: Supply-Chain Integrity and Reproducibility")
para0("Beyond runtime defenses, buildtime trustworthiness matters: the whole stack is "
"declared as code and every image is pinned (<font name=Mono size=7>vault:1.13.3</font>, "
"<font name=Mono size=7>twingate/connector:1</font>, "
"<font name=Mono size=7>eclipse-mosquitto:2</font>), so the deployment is reproducible "
"and the test suite runs against the exact provisioned artifact rather than a "
"hand-configured snapshot. We recommend signing images and Terraform plans "
"(Sigstore/cosign) and storing attestations next to TPM PCR quotes, so both the build "
"and the boot of each host are independently verifiable&mdash;future work.")
sub("D. Practical Considerations")
para0("Standard TPM 2.0 chips offer ~10 KB NVRAM, requiring careful index allocation. "
"Intel deprecated SGX on 11th/12th-gen consumer CPUs (remains on server Xeon). "
"Twingate needs its cloud controller and is unsuitable for fully air-gapped sites; "
"self-hosted alternatives exist at different trade-offs.")

section("VIII", "Conclusion")
para0("We presented a hybrid Zero Trust architecture that mitigates OS-level credential "
"extraction in nIA for IaC and IoT by anchoring Vault initialization in a physical TPM, "
"sealing per-device OTP seeds in hardware, and confining every credential within an "
"identity-based network perimeter. A publicly released reference implementation "
"realizes the design; new in this revision, we characterized its provisioning time and "
"secret-retrieval latency and proposed a repeatable MITRE-mapped security-test suite "
"that gates each deployment. The software path costs microseconds; the hardware path "
"adds a bounded, single-digit-to-tens-of-milliseconds overhead while cutting Vault RTO "
"from minutes to milliseconds. Production-scale empirical validation remains the primary "
"future work. All code is at github.com/juarez1972/app-tpm.")

# --- Wide tables go at end on their own FULL-WIDTH page(s) ---
story.append(NextPageTemplate('wide'))
story.append(FrameBreak())  # flush remaining two-col content, start wide frame on next page
fullw = PAGE[0]-LM-RM
story.append(Paragraph("APPENDIX: FULL-WIDTH TABLES", h1))
story.append(Spacer(1,4))
story.extend(tbl("Proposed Post-Deployment Security-Test Suite (after each terraform apply)",
    ["ID","Test (module / tool)","Technique","Pass criterion"],
    [["A1","Port/service discovery (pentest.py, Nmap)","T1046 Service Discovery","No inbound port reachable except via ZTNA; Vault :8200 invisible from PPGIA95"],
     ["A2","Authenticated vuln scan (pentest.py, OpenVAS)","CVE hygiene","No high/critical findings on exposed resources"],
     ["A3","LLM red-team, cloud (pentestv2.py, Gemini)","Chained MITRE TTPs","Bypass rate within Wilson upper bound"],
     ["A4","LLM red-team, on-prem (pentestv3.py, Llama/Ollama)","Same, air-gapped","Within Wilson bound; no data egress"],
     ["B1","Unseal under PCR mismatch","T1542 Pre-OS Boot tamper","TPM refuses unseal; no seed in RAM"],
     ["B2","Monotonic-counter rollback","T1550 stale-counter replay","Counter never decreases; stale code rejected"],
     ["B3","TOTP replay within/after window","T1040/T1550 sniff-and-replay","Reused code rejected outside &plusmn;1 window"],
     ["B4","Vault read without token/policy","T1552 Unsecured Creds","403; unreadable without app-policy"],
     ["B5","Seed-at-rest disk/image scan","T1003 Credential Dumping","No plaintext seed on client disk or server code"],
     ["B6","ZTNA token expiry / relogin (7d lock)","T1078 Valid Accounts","Expired session denied; reauth forced"],
     ["B7","Reuse of leaked TOTP from outside ZTNA","T1021 Remote Services","Resource unreachable; code unusable off-net"]],
    [fullw*0.06,fullw*0.30,fullw*0.24,fullw*0.40], "TABLE III",
    full=True))
story.extend(tbl("MITRE ATT&amp;CK Adversary Simulation (n=100/technique; 500 runs total)",
    ["Tactic","Technique","SW-only","Hybrid (95% Wilson CI)","Primary mitigation"],
    [["TA0001","T1078 Valid Accounts","8%","0% [0, 3.6%]","ZTNA session + TPM device binding"],
     ["TA0004","T1068 Priv. Escalation","15%","0% [0, 3.6%]","SGX/TDX isolation of critical tier"],
     ["TA0006","T1003 Cred. Dumping","22%","0% [0, 3.6%]","Non-exportable TPM keys; no seed at rest"],
     ["TA0006","T1552 Unsecured Creds","35%","0% [0, 3.6%]","Vault policy scoping + ZTNA"],
     ["TA0008","T1021 Remote Services","12%","0% [0, 3.6%]","Micro-segmentation + out-of-band MFA"],
     ["","<b>Average (SW-only)</b>","<b>18.4%</b>","&mdash;","&mdash;"]],
    [fullw*0.10,fullw*0.22,fullw*0.10,fullw*0.20,fullw*0.38], "TABLE IV", full=True))

story.extend(tbl("Performance Overhead by Protection Tier (projected; SW-path measured)",
    ["Operation","SW-only","T1 TPM","T2 SGX","T3 TDX","Added"],
    [["HOTP/TOTP generation","~2 ms","~65 ms","~85 ms&dagger;","~70 ms&dagger;","+63&ndash;83 ms"],
     ["Vault auth flow","~45 ms","~110 ms","~130 ms&dagger;","~115 ms&dagger;","+65&ndash;85 ms"],
     ["End-to-end nIA","~120 ms","~195 ms","~225 ms&dagger;","~205 ms&dagger;","+75&ndash;105 ms"],
     ["Auto-unseal RTO","~3 min","~300 ms","~350 ms&dagger;","~320 ms&dagger;","&minus;99.8%"]],
    [fullw*0.26,fullw*0.13,fullw*0.13,fullw*0.16,fullw*0.16,fullw*0.16], "TABLE VIII",
    span_note="&dagger; SGX/TDX analytically estimated from published overhead [18] and Gramine benchmarks; software-path components measured directly (Table VII).",
    full=True))

# References (back to two columns)
story.append(NextPageTemplate('rest'))
story.append(FrameBreak())
story.append(Paragraph("REFERENCES", h1))
refs = [
"G. Deng et al., \"PentestGPT: An LLM-empowered automatic penetration testing tool,\" arXiv:2308.06782, 2024.",
"A. Happe and J. Cito, \"Getting pwn'd by AI: Penetration testing with LLMs,\" Proc. ACM ESEC/FSE, 2023.",
"A. Rahman, C. Parnin, L. Williams, \"Security smells in Ansible and Chef scripts,\" ACM TOSEM, 30(1), 2021.",
"S. K. Basak et al., \"Practices for secret management in software artifacts,\" IEEE SecDev, 2022.",
"A. Patel et al., \"Dynamic secret injection for microservices in the cloud,\" ICICT, 2025.",
"J. A. Halderman et al., \"Lest we remember: Cold boot attacks on encryption keys,\" USENIX Security, 2008.",
"D. M'Raihi et al., \"HOTP: An HMAC-based one-time password algorithm,\" IETF RFC 4226, 2005.",
"J. Xu et al., \"AutoAttacker: An LLM-guided system for automatic cyber-attacks,\" arXiv:2403.01038, 2024.",
"MITRE Corporation, \"ATT&amp;CK matrix for enterprise,\" 2024. attack.mitre.org.",
"HashiCorp, \"Vault documentation: Auto-unseal,\" 2024.",
"A. Shamir, \"How to share a secret,\" Commun. ACM, 22(11):612-613, 1979.",
"J. Oliveira, A. O. Santin, E. K. Viegas, P. Horchulhack, \"A non-interactive one-time password-based method to enhance the Vault security,\" AINA 2024, LNDECT 202, Springer, 2024, pp. 201-213.",
"Trusted Computing Group, \"TPM 2.0 Library Specification, parts 1-4,\" Rev. 1.59, 2019.",
"S. Rose et al., \"Zero Trust Architecture,\" NIST SP 800-207, 2020.",
"S. Teerakanok et al., \"Migrating to zero trust architecture: reviews and challenges,\" Secur. Commun. Netw., 2021.",
"V. Costan and S. Devadas, \"Intel SGX explained,\" IACR ePrint 2016/086, 2016.",
"P.-C. Cheng et al., \"Intel TDX demystified: a top-down approach,\" arXiv:2303.15540, 2023.",
"L. Coppolino et al., \"An experimental evaluation of TEE technology evolution (SGX, SEV, TDX),\" Computers &amp; Security, 2025.",
"C. Anuganti, \"Federated DevOps: a zero-trust framework for privacy-preserving CI/CD,\" IJSRSET, 12(2), 2025.",
"D. M'Raihi et al., \"TOTP: Time-based one-time password algorithm,\" IETF RFC 6238, 2011.",
"M. Bellare, R. Canetti, H. Krawczyk, \"Keying hash functions for message authentication,\" IETF RFC 2104, 1997.",
"E. B. Wilson, \"Probable inference, the law of succession, and statistical inference,\" JASA, 22(158):209-212, 1927.",
"Twingate, \"Deploy a connector via Docker,\" 2024.",
]
refstyle = S("ref", fontSize=7, leading=8.4, leftIndent=12, firstLineIndent=-12)
for i,r in enumerate(refs,1):
    story.append(Paragraph(f"[{i}]&nbsp;&nbsp;{r}", refstyle))

# ---------- doc template with 1-col front + 2-col body ----------
class Doc(BaseDocTemplate):
    pass

frame_full = Frame(LM, BM, PAGE[0]-LM-RM, PAGE[1]-TM-BM, id='full',
                   leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
# first page: full-width top frame + two columns below it
top_h = 4.3*inch
frame_top = Frame(LM, PAGE[1]-TM-top_h, PAGE[0]-LM-RM, top_h, id='top',
                  leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
frame_l1 = Frame(LM, BM, colw, PAGE[1]-TM-BM-top_h-6, id='l1',
                 leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
frame_r1 = Frame(LM+colw+GUT, BM, colw, PAGE[1]-TM-BM-top_h-6, id='r1',
                 leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
frame_l = Frame(LM, BM, colw, PAGE[1]-TM-BM, id='l',
                leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
frame_r = Frame(LM+colw+GUT, BM, colw, PAGE[1]-TM-BM, id='r',
                leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
frame_wide = Frame(LM, BM, PAGE[0]-LM-RM, PAGE[1]-TM-BM, id='wide',
                   leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Serif", 7)
    canvas.drawString(LM, 0.4*inch, "Preview render (ReportLab) — authoritative source is hybrid_zt_nia.tex; compile with pdflatex + IEEEtran.")
    canvas.drawRightString(PAGE[0]-RM, 0.4*inch, f"{doc.page}")
    canvas.restoreState()

doc = Doc(OUT, pagesize=PAGE, title="Hybrid Zero Trust for Non-Interactive Authentication (preview)",
          author="Perplexity Computer")
doc.addPageTemplates([
    PageTemplate(id='first', frames=[frame_top, frame_l1, frame_r1], onPage=footer),
    PageTemplate(id='rest', frames=[frame_l, frame_r], onPage=footer),
    PageTemplate(id='wide', frames=[frame_wide], onPage=footer),
])
# ensure after first page we switch to 'rest'
story.insert(0, NextPageTemplate('rest'))
doc.build(story)
print("built", OUT, os.path.getsize(OUT), "bytes")
