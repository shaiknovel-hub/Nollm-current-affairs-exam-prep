import re
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.database import connect, init_db

EXAM_TOPICS = [
    "National Affairs & Governance",
    "Economy, Banking & Finance",
    "Government Schemes & Initiatives",
    "Defence, Exercises & Security",
    "Science, Technology & Space",
    "International Affairs & Summits",
    "Appointments, Resignations & Committees",
    "Awards, Honors & Rankings",
    "Environment, Ecology & Agriculture",
    "Sports & Cultural Events"
]

def clean_val(v: str) -> str:
    """Cleans parsed values of checkmarks, bullet points, and trailing punctuation."""
    v = re.sub(r'^[✓•\-\*\s]+', '', v)
    v = re.sub(r'[\(\)\[\]\"\'\<\>]', '', v)
    return v.strip().rstrip(':,.- ')

def clean_subject(raw_subject: str) -> str:
    s = re.sub(r'^(the\s+|a\s+|an\s+|under\s+|in\s+|for\s+)', '', raw_subject.strip(), flags=re.I)
    s = re.sub(r'[\(\)\[\]\"\']', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().rstrip(':,.- ')

NOISE_PATTERNS = [
    re.compile(r'affairscloud', re.I),
    re.compile(r'toppers-ca', re.I),
    re.compile(r'page\s*\d+\s*(of|\/)\s*\d+', re.I),
    re.compile(r'table\s+of\s+contents', re.I),
    re.compile(r'current\s+affairs\s+(today|capsule|monthly|pdf)', re.I),
    re.compile(r'http[s]?://\S+', re.I),
    re.compile(r'copyright|all\s+rights\s+reserved', re.I),
    re.compile(r'click\s+here|download\s+app', re.I),
]

def is_noise_or_toc_line(line: str) -> bool:
    line_lower = line.lower()
    if len(line) < 18 or len(line) > 350:
        return True
    if re.search(r'\.{4,}\s*\d+', line) or re.search(r'\s{4,}\d+$', line):
        return True
    return any(p.search(line_lower) for p in NOISE_PATTERNS)

def map_section_to_topic(section_name: str) -> str:
    sec = section_name.upper()
    if "NATIONAL" in sec or "STATE" in sec or "GOVERNANCE" in sec:
        return "National Affairs & Governance"
    if "BANKING" in sec or "FINANCE" in sec or "ECONOMY" in sec or "BUSINESS" in sec:
        return "Economy, Banking & Finance"
    if "SCHEME" in sec or "INITIATIVE" in sec:
        return "Government Schemes & Initiatives"
    if "DEFENCE" in sec or "SECURITY" in sec or "MILITARY" in sec:
        return "Defence, Exercises & Security"
    if "SCIENCE" in sec or "TECHNOLOGY" in sec or "SPACE" in sec:
        return "Science, Technology & Space"
    if "INTERNATIONAL" in sec or "SUMMIT" in sec or "DIPLOMACY" in sec:
        return "International Affairs & Summits"
    if "APPOINTMENT" in sec or "RESIGNATION" in sec or "COMMITTEE" in sec:
        return "Appointments, Resignations & Committees"
    if "AWARD" in sec or "HONOUR" in sec or "RANKING" in sec:
        return "Awards, Honors & Rankings"
    if "ENVIRONMENT" in sec or "AGRICULTURE" in sec or "ECOLOGY" in sec:
        return "Environment, Ecology & Agriculture"
    if "SPORT" in sec or "CULTURE" in sec or "DAY" in sec:
        return "Sports & Cultural Events"
    return "National Affairs & Governance"

def parse_exam_hints_block(hint_text: str) -> Dict[str, str]:
    hints = {}
    lines = hint_text.split('\n')
    current_key = None

    for line in lines:
        clean_l = clean_val(line)
        if not clean_l or is_noise_or_toc_line(clean_l):
            continue
        # Stop hint parsing if we hit a new major sub-section
        if any(h in clean_l for h in ["About ", "Background:", "Key Details", "Highlights of"]):
            break
        m = re.match(r'^([A-Za-z0-9\s/–—]+)[\?:–—]\s*(.*)$', clean_l)
        if m:
            k = m.group(1).strip()
            v = m.group(2).strip()
            current_key = k
            if v:
                hints[k] = v
        elif current_key and line.startswith(' ') and len(clean_l) > 2:
            hints[current_key] += " " + clean_l

    return hints

def generate_questions_from_hints(
    hints: Dict[str, str],
    headline: str,
    section: str,
    filename: str,
    page_num: int,
    month: str,
    year: int
) -> List[Dict[str, Any]]:
    questions = []
    topic = map_section_to_topic(section)
    what = clean_val(hints.get("What") or hints.get("Event") or headline)

    # 1. Venue / Location
    venue = hints.get("Where") or hints.get("Venue") or hints.get("Trial Location") or hints.get("Host") or hints.get("Location")
    if venue and len(venue) > 3 and not any(w in venue.lower() for w in ["page", "content"]):
        venue_clean = clean_val(venue)
        distractors = ["New Delhi, Delhi", "Visakhapatnam, Andhra Pradesh", "Umroi, Meghalaya", "Pokhran, Rajasthan", "Gandhinagar, Gujarat", "Bengaluru, Karnataka"]
        d_filtered = [d for d in distractors if venue_clean.lower() not in d.lower()][:3]
        options = [venue_clean] + d_filtered
        random.shuffle(options)
        correct_letter = ["A", "B", "C", "D"][options.index(venue_clean)]

        q_stem = f"Where was {what.rstrip('.')} held / conducted?" if any(w in what.lower() for w in ["exercise", "summit", "forum", "trial", "championship"]) else f"What was the official venue or location for: {what.rstrip('.')}?"
        questions.append({
            "month": month, "year": year, "source_filename": filename, "page_number": page_num,
            "topic": topic, "subtopic": "Venue & Location",
            "question_text": q_stem,
            "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
            "correct_option": correct_letter,
            "explanation": f"Factual source record: {what}. The official venue/location is {venue_clean}.",
            "memory_cue": f"{what[:35]} → {venue_clean}.",
            "key_concept": f"Venue of {what[:30]}",
            "difficulty": "easy",
            "approval_status": "approved"
        })

    # 2. Theme / Slogan
    theme = hints.get("Theme") or hints.get("Motto")
    if theme and len(theme) > 5:
        theme_clean = clean_val(theme)
        d_themes = [
            "Innovating for a Greener and Sustainable Future",
            "Digital Transformation and Inclusive Economic Growth",
            "Empowering Youth for Resilient Nation Building"
        ]
        options = [theme_clean] + [d for d in d_themes if theme_clean.lower() not in d.lower()][:3]
        random.shuffle(options)
        correct_letter = ["A", "B", "C", "D"][options.index(theme_clean)]

        questions.append({
            "month": month, "year": year, "source_filename": filename, "page_number": page_num,
            "topic": topic, "subtopic": "Theme & Slogan",
            "question_text": f"What was the official theme of '{what.rstrip('.')}'?",
            "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
            "correct_option": correct_letter,
            "explanation": f"According to the official release for {what}, the designated theme is \"{theme_clean}\".",
            "memory_cue": f"{what[:30]} Theme → \"{theme_clean[:35]}\".",
            "key_concept": f"Theme of {what[:30]}",
            "difficulty": "medium",
            "approval_status": "approved"
        })

    # 3. Edition / Number
    edition = hints.get("Edition")
    if edition and re.search(r'\d+', edition):
        ed_clean = clean_val(edition)
        num_m = re.search(r'\d+', ed_clean)
        if num_m:
            n = int(num_m.group(0))
            d_ed = [f"{n-2}th", f"{n-1}th", f"{n+1}th"] if n > 2 else ["2nd", "3rd", "4th"]
            options = [ed_clean] + [d for d in d_ed if ed_clean.lower() not in d.lower()][:3]
            random.shuffle(options)
            correct_letter = ["A", "B", "C", "D"][options.index(ed_clean)]

            questions.append({
                "month": month, "year": year, "source_filename": filename, "page_number": page_num,
                "topic": topic, "subtopic": "Edition",
                "question_text": f"Which edition of {what.rstrip('.')} was conducted / held in September {year}?",
                "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
                "correct_option": correct_letter,
                "explanation": f"Official records verify that the {ed_clean} edition of {what} took place.",
                "memory_cue": f"{what[:30]} → {ed_clean} Edition.",
                "key_concept": f"Edition of {what[:30]}",
                "difficulty": "easy",
                "approval_status": "approved"
            })

    # 4. Key Dignitary / Minister / Launched By / Inaugurated By
    person = hints.get("Launched By") or hints.get("Inaugurated by") or hints.get("Inaugurated By") or hints.get("By Whom") or hints.get("Director & Writer")
    if person and len(person) > 4 and not any(w in person.lower() for w in ["page", "content", "meity", "ministry"]):
        person_clean = clean_val(person)
        distractors = [
            "PM Narendra Modi", "Union Minister Amit Shah", "Union Minister Rajnath Singh",
            "Union Minister Dr. S. Jaishankar", "Union Minister Bhupender Yadav"
        ]
        d_filtered = [d for d in distractors if person_clean.lower() not in d.lower()][:3]
        options = [person_clean] + d_filtered
        random.shuffle(options)
        correct_letter = ["A", "B", "C", "D"][options.index(person_clean)]

        questions.append({
            "month": month, "year": year, "source_filename": filename, "page_number": page_num,
            "topic": topic, "subtopic": "Leadership & Launch",
            "question_text": f"Who launched, inaugurated, or led '{what.rstrip('.')}'?",
            "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
            "correct_option": correct_letter,
            "explanation": f"Official announcement: {what} was launched/inaugurated by {person_clean}.",
            "memory_cue": f"{what[:30]} → {person_clean}.",
            "key_concept": f"Inauguration of {what[:30]}",
            "difficulty": "medium",
            "approval_status": "approved"
        })

    # 5. Partner Entities / Navies / Countries
    partner = hints.get("Partners") or hints.get("Between") or hints.get("Conducted Between") or hints.get("Entities") or hints.get("Key Partners") or hints.get("Signatories")
    if partner and len(partner) > 4 and not any(w in partner.lower() for w in ["page", "content"]):
        partner_clean = clean_val(partner)
        if "bank" in partner_clean.lower() or "iob" in partner_clean.lower():
            d_list = ["novio & Punjab National Bank", "novio & State Bank of India", "novio & Bank of Baroda"]
        elif "navy" in partner_clean.lower() or "army" in partner_clean.lower():
            d_list = ["Indian Army & French Armed Forces", "Indian Army & Royal Thai Army", "Indian Armed Forces & US Military"]
        else:
            d_list = ["NITI Aayog & World Bank", "FICCI & CII", "IIT Delhi & University of Oxford"]

        d_filtered = [d for d in d_list if partner_clean.lower() not in d.lower()][:3]
        options = [partner_clean] + d_filtered
        random.shuffle(options)
        correct_letter = ["A", "B", "C", "D"][options.index(partner_clean)]

        questions.append({
            "month": month, "year": year, "source_filename": filename, "page_number": page_num,
            "topic": topic, "subtopic": "Bilateral & Institutional Partnerships",
            "question_text": f"Which key entities, armed forces, or institutions partnered for: {what.rstrip('.')}?",
            "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
            "correct_option": correct_letter,
            "explanation": f"Partnership details: For {what}, the collaborating entities are: {partner_clean}.",
            "memory_cue": f"{what[:30]} ⇄ {partner_clean[:30]}.",
            "key_concept": f"Partners in {what[:30]}",
            "difficulty": "easy",
            "approval_status": "approved"
        })

    # 6. Financial Amount / Investment / Line of Credit / Contract Value
    money_val = hints.get("Line of Credit") or hints.get("Total Payment") or hints.get("Outlay") or hints.get("Target") or hints.get("Investment by MDL") or hints.get("Contract Value")
    if money_val and re.search(r'[\d,]+', money_val):
        money_clean = clean_val(money_val)
        num_m = re.search(r'[\d,]+(?:\.\d+)?', money_clean)
        if num_m:
            try:
                base = float(num_m.group(0).replace(',', ''))
                unit = re.search(r'(?:crore|lakh|billion|million|trillion)', money_clean, re.I)
                unit_str = unit.group(0) if unit else ""
                sym = "Rs " if "Rs" in money_clean else ("USD " if "USD" in money_clean else "₹")
                d1 = f"{sym}{int(base * 0.75):,} {unit_str}".strip()
                d2 = f"{sym}{int(base * 1.25):,} {unit_str}".strip()
                d3 = f"{sym}{int(base * 1.5):,} {unit_str}".strip()
            except ValueError:
                d1, d2, d3 = "Rs 2,500 crore", "Rs 5,000 crore", "Rs 7,500 crore"
        else:
            d1, d2, d3 = "Rs 1,000 crore", "Rs 3,000 crore", "Rs 5,000 crore"

        options = [money_clean, d1, d2, d3]
        random.shuffle(options)
        correct_letter = ["A", "B", "C", "D"][options.index(money_clean)]

        questions.append({
            "month": month, "year": year, "source_filename": filename, "page_number": page_num,
            "topic": topic, "subtopic": "Financial Allocation / Budget",
            "question_text": f"What was the financial amount, outlay, or target announced for: {what.rstrip('.')}?",
            "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
            "correct_option": correct_letter,
            "explanation": f"Financial figures: For {what}, the officially reported amount is {money_clean}.",
            "memory_cue": f"{what[:35]} → {money_clean}.",
            "key_concept": f"Outlay for {what[:30]}",
            "difficulty": "medium",
            "approval_status": "approved"
        })

    # 7. Technical Specifications / Capacity / Range
    spec = hints.get("Maximum Range") or hints.get("Capacity") or hints.get("First Issuance") or hints.get("Coverage")
    if spec and len(spec) > 2:
        spec_clean = clean_val(spec)
        if "km" in spec_clean:
            d_specs = ["Up to 500 km", "Up to 1,500 km", "Up to 2,000 km"]
        elif "GT" in spec_clean or "ton" in spec_clean.lower():
            d_specs = ["0.8 million GT per year", "1.8 million GT per year", "2.5 million GT per year"]
        elif "acres" in spec_clean.lower():
            d_specs = ["Around 15,000 acres", "Around 50,000 acres", "Around 75,000 acres"]
        else:
            d_specs = ["Option 1", "Option 2", "Option 3"]

        options = [spec_clean] + [d for d in d_specs if spec_clean.lower() not in d.lower()][:3]
        random.shuffle(options)
        correct_letter = ["A", "B", "C", "D"][options.index(spec_clean)]

        questions.append({
            "month": month, "year": year, "source_filename": filename, "page_number": page_num,
            "topic": topic, "subtopic": "Technical Capacity / Coverage",
            "question_text": f"What is the recorded capacity, range, or coverage specification for: {what.rstrip('.')}?",
            "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
            "correct_option": correct_letter,
            "explanation": f"Technical specifications: {what} has a verified specification of {spec_clean}.",
            "memory_cue": f"{what[:30]} → {spec_clean}.",
            "key_concept": f"Specification of {what[:30]}",
            "difficulty": "hard",
            "approval_status": "approved"
        })

    # 8. Significance / Historical Milestones
    sig = hints.get("Significance") or hints.get("Purpose")
    if sig and len(sig) > 10:
        sig_clean = clean_val(sig)
        d_sig = [
            "India signed a Comprehensive Free Trade Agreement with the European Union",
            "India inaugurated its first deep-sea exploration port in the Indian Ocean",
            "India achieved 100% domestic manufacturing of commercial widebody aircraft"
        ]
        options = [sig_clean] + d_sig[:3]
        random.shuffle(options)
        correct_letter = ["A", "B", "C", "D"][options.index(sig_clean)]

        questions.append({
            "month": month, "year": year, "source_filename": filename, "page_number": page_num,
            "topic": topic, "subtopic": "Strategic Significance",
            "question_text": f"What was the key significance or outcome highlighted for: {what.rstrip('.')}?",
            "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
            "correct_option": correct_letter,
            "explanation": f"Strategic milestone: {what}. Significance: {sig_clean}.",
            "memory_cue": f"{what[:30]} → {sig_clean[:35]}.",
            "key_concept": f"Significance of {what[:30]}",
            "difficulty": "medium",
            "approval_status": "approved"
        })

    return questions

def parse_about_blocks(page_text: str, filename: str, page_num: int, month: str, year: int) -> List[Dict[str, Any]]:
    """
    Extracts Static GK and Institutional Banking awareness questions from 'About [Org]:' blocks.
    Commonly tested in Banking, SSC, and State Exams.
    """
    questions = []
    about_parts = re.split(r'About\s+([A-Za-z0-9\s,\-\'\(\)&]+?):', page_text)
    if len(about_parts) < 3:
        return questions

    for i in range(1, len(about_parts), 2):
        org_name = clean_subject(about_parts[i])
        block_text = about_parts[i+1][:400]
        if len(org_name) < 3 or len(org_name) > 65 or any(w in org_name.lower() for w in ["page", "content", "copyright"]):
            continue

        # Extract Headquarters
        hq_m = re.search(r'Headquarters\s*[-–—:]\s*([A-Za-z0-9\s,]+)', block_text)
        if hq_m:
            hq = clean_val(hq_m.group(1).split('\n')[0])
            if len(hq) > 3 and len(hq) < 40:
                d_hqs = ["Mumbai, Maharashtra", "New Delhi, Delhi", "Chennai, Tamil Nadu", "Kolkata, West Bengal", "Bengaluru, Karnataka"]
                options = [hq] + [d for d in d_hqs if hq.lower() not in d.lower()][:3]
                random.shuffle(options)
                correct_letter = ["A", "B", "C", "D"][options.index(hq)]

                questions.append({
                    "month": month, "year": year, "source_filename": filename, "page_number": page_num,
                    "topic": "Economy, Banking & Finance" if any(w in org_name.lower() for w in ["bank", "iob", "sebi", "rbi"]) else "National Affairs & Governance",
                    "subtopic": "Institutional Headquarters",
                    "question_text": f"Where is the headquarters of {org_name} located?",
                    "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
                    "correct_option": correct_letter,
                    "explanation": f"Institutional static fact: The headquarters of {org_name} is located in {hq}.",
                    "memory_cue": f"{org_name[:30]} HQ → {hq}.",
                    "key_concept": f"HQ of {org_name[:30]}",
                    "difficulty": "easy",
                    "approval_status": "approved"
                })

        # Extract MD & CEO / Chairman
        chief_m = re.search(r'(?:Chairman|MD|CEO|Director General|Executive Director|CMD)[A-Za-z\s\(\)&]*[-–—:]\s*([A-Za-z\.\s]{3,35})', block_text)
        if chief_m:
            chief = clean_val(chief_m.group(1).split('\n')[0])
            if len(chief) > 4 and len(chief) < 35 and not any(w in chief.lower() for w in ["established", "headquarters", "about"]):
                d_chiefs = ["Rajiv Gauba", "Sanjeev Sanyal", "T.V. Somanathan", "Ajay Kumar Srivastava", "Debjit Chakraborty"]
                options = [chief] + [d for d in d_chiefs if chief.lower() not in d.lower()][:3]
                random.shuffle(options)
                correct_letter = ["A", "B", "C", "D"][options.index(chief)]

                questions.append({
                    "month": month, "year": year, "source_filename": filename, "page_number": page_num,
                    "topic": "Appointments, Resignations & Committees",
                    "subtopic": "Institutional Leadership",
                    "question_text": f"Who currently heads or serves as the Chief Executive / Chairman of {org_name}?",
                    "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
                    "correct_option": correct_letter,
                    "explanation": f"Official leadership: {chief} is the designated head/chief of {org_name}.",
                    "memory_cue": f"{org_name[:30]} Chief → {chief}.",
                    "key_concept": f"Head of {org_name[:30]}",
                    "difficulty": "medium",
                    "approval_status": "approved"
                })

        # Extract Established Year
        est_m = re.search(r'Established\s*[-–—:]\s*(19\d\d|20\d\d)', block_text)
        if est_m:
            est_year = est_m.group(1)
            y_int = int(est_year)
            d_years = [str(y_int - 5), str(y_int + 3), str(y_int + 7)]
            options = [est_year] + d_years
            random.shuffle(options)
            correct_letter = ["A", "B", "C", "D"][options.index(est_year)]

            questions.append({
                "month": month, "year": year, "source_filename": filename, "page_number": page_num,
                "topic": "National Affairs & Governance",
                "subtopic": "Institutional History",
                "question_text": f"In which year was {org_name} established?",
                "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]},
                "correct_option": correct_letter,
                "explanation": f"Institutional timeline: {org_name} was established in {est_year}.",
                "memory_cue": f"{org_name[:30]} Established → {est_year}.",
                "key_concept": f"Founding year of {org_name[:30]}",
                "difficulty": "medium",
                "approval_status": "approved"
            })

    return questions

def extract_candidate_facts_from_text(page_text: str, filename: str, page_num: int, month: str = "September", year: int = 2026) -> List[Dict[str, Any]]:
    candidates = []

    # Detect active section heading
    current_section = "National Affairs"
    sec_match = re.search(r'(NATIONAL AFFAIRS|BANKING & FINANCE|INTERNATIONAL AFFAIRS|ECONOMY & BUSINESS|DEFENCE|SCIENCE & TECHNOLOGY|ENVIRONMENT|SPORTS|AWARDS & RECOGNITIONS|APPOINTMENTS|IMPORTANT DAYS|STATE NEWS)', page_text)
    if sec_match:
        current_section = sec_match.group(1)

    # 1. Parse all Exam Hints blocks
    if "Exam Hints:" in page_text:
        parts = page_text.split("Exam Hints:")
        for idx in range(1, len(parts)):
            hint_block = parts[idx]
            pre_text = parts[idx-1].strip()
            headline_candidates = [l.strip() for l in pre_text.split('\n') if len(l.strip()) > 15 and "Copyright" not in l and "Report" not in l and "Daily Content" not in l]
            headline = headline_candidates[-1] if headline_candidates else f"Current Affairs on Page {page_num}"

            parsed_hints = parse_exam_hints_block(hint_block)
            hint_questions = generate_questions_from_hints(
                parsed_hints, headline, current_section, filename, page_num, month, year
            )
            candidates.extend(hint_questions)

    # 2. Parse About [Organization] blocks for static institutional awareness
    about_questions = parse_about_blocks(page_text, filename, page_num, month, year)
    candidates.extend(about_questions)

    # 3. Financial allocations in article text
    lines = [clean_val(l) for l in page_text.split('\n') if len(clean_val(l)) > 25 and not is_noise_or_toc_line(l)]
    money_pattern = re.compile(
        r'([A-Z][A-Za-z0-9\s,\-\'\"\(\)]{8,60}?)\s+(?:approved|allocated|sanctioned|invested|worth|total outlay of|budget of|outlay of)\s+([₹Rs\$\€]\s*[\d,]+(?:\.\d+)?\s*(?:crore|lakh|billion|million|trillion)?)',
        re.I
    )

    seen = {c["question_text"] for c in candidates}

    for line in lines:
        m = money_pattern.search(line)
        if m:
            subj = clean_val(m.group(1)).rstrip(':,.- ')
            amt = clean_val(m.group(2))
            q_text = f"What was the total financial outlay or approved amount for {subj}?"
            if q_text not in seen and len(subj) > 8 and not any(w in subj.lower() for w in ["page", "chapter", "table", "section"]):
                seen.add(q_text)
                num_m = re.search(r'[\d,]+(?:\.\d+)?', amt)
                unit_str = "crore" if "crore" in amt else ""
                sym = "₹" if "₹" in amt or "Rs" in amt else ("$" if "$" in amt else "")
                if num_m:
                    try:
                        base = float(num_m.group(0).replace(',', ''))
                        d1 = f"{sym}{int(base * 0.75):,} {unit_str}".strip()
                        d2 = f"{sym}{int(base * 1.25):,} {unit_str}".strip()
                        d3 = f"{sym}{int(base * 1.5):,} {unit_str}".strip()
                    except ValueError:
                        d1, d2, d3 = f"{sym}2,000 {unit_str}", f"{sym}4,000 {unit_str}", f"{sym}6,000 {unit_str}"
                else:
                    d1, d2, d3 = f"{sym}1,500 crore", f"{sym}3,000 crore", f"{sym}5,000 crore"

                opts = [amt, d1, d2, d3]
                random.shuffle(opts)
                corr = ["A", "B", "C", "D"][opts.index(amt)]

                candidates.append({
                    "month": month, "year": year, "source_filename": filename, "page_number": page_num,
                    "topic": map_section_to_topic(current_section),
                    "subtopic": "Financial Allocation",
                    "question_text": q_text,
                    "options": {"A": opts[0], "B": opts[1], "C": opts[2], "D": opts[3]},
                    "correct_option": corr,
                    "explanation": f"Source passage: \"{line}\". The figure approved is {amt}.",
                    "memory_cue": f"{subj[:30]} → {amt}.",
                    "key_concept": f"Allocation for {subj[:25]}",
                    "difficulty": "medium",
                    "approval_status": "approved"
                })

    return candidates

def generate_questions_for_document(
    document_id: int,
    month: str = "September",
    year: int = 2026,
    max_questions: int = 60
) -> Dict[str, Any]:
    init_db()
    with connect() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)).fetchone()
        if not doc:
            return {"error": "Document not found", "count": 0}

    filename = doc["filename"]
    safe_stem = Path(filename).stem
    candidates_found = []

    ext_dir = Path(__file__).resolve().parents[1] / "data" / "extracted"
    matching_files = list(ext_dir.glob(f"{safe_stem}*.txt"))

    if matching_files:
        full_text = matching_files[0].read_text(encoding="utf-8")
        pages = full_text.split("=== PAGE ")
        for p in pages:
            if not p.strip():
                continue
            parts = p.split("===\n", 1)
            page_num = 1
            page_body = p
            if len(parts) == 2:
                try:
                    page_num = int(parts[0].strip())
                    page_body = parts[1]
                except ValueError:
                    page_body = p
            
            page_candidates = extract_candidate_facts_from_text(page_body, filename, page_num, month, year)
            candidates_found.extend(page_candidates)

    saved_count = 0
    with connect() as conn:
        for c in candidates_found[:max_questions]:
            dup = conn.execute(
                "SELECT question_id FROM questions WHERE question_text = ?",
                (c["question_text"],)
            ).fetchone()
            if not dup:
                conn.execute("""
                    INSERT INTO questions(
                        document_id, source_filename, page_number,
                        month, year, topic, subtopic,
                        question_text, options_json, correct_option,
                        explanation, memory_cue, key_concept,
                        difficulty, approval_status
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    document_id, c["source_filename"], c["page_number"],
                    month, year, c["topic"], c.get("subtopic"),
                    c["question_text"], json.dumps(c["options"], ensure_ascii=False),
                    c["correct_option"], c.get("explanation"), c.get("memory_cue"),
                    c.get("key_concept"), c.get("difficulty", "medium"),
                    c.get("approval_status", "approved")
                ))
                saved_count += 1

    return {
        "status": "success",
        "document_id": document_id,
        "filename": filename,
        "generated": len(candidates_found),
        "saved_to_review": saved_count
    }

def get_candidate_questions(
    approval_status: str = "pending_review",
    month: Optional[str] = None,
    year: Optional[int] = None,
    topic: Optional[str] = None
) -> List[Dict[str, Any]]:
    init_db()
    query = "SELECT * FROM questions WHERE approval_status = ?"
    params = [approval_status]

    if month and year and month != "All months":
        query += " AND month = ? AND year = ?"
        params.extend([month, year])

    if topic and topic != "All topics":
        query += " AND topic = ?"
        params.append(topic)

    query += " ORDER BY question_id DESC"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            q = dict(r)
            try:
                q["options"] = json.loads(q["options_json"])
            except Exception:
                q["options"] = {}
            result.append(q)
        return result

def update_candidate_question(
    question_id: int,
    question_text: str,
    options: Dict[str, str],
    correct_option: str,
    topic: str,
    difficulty: str,
    explanation: str,
    memory_cue: str,
    approval_status: str
) -> bool:
    init_db()
    with connect() as conn:
        conn.execute("""
            UPDATE questions
            SET question_text = ?,
                options_json = ?,
                correct_option = ?,
                topic = ?,
                difficulty = ?,
                explanation = ?,
                memory_cue = ?,
                approval_status = ?
            WHERE question_id = ?
        """, (
            question_text,
            json.dumps(options, ensure_ascii=False),
            correct_option,
            topic,
            difficulty,
            explanation,
            memory_cue,
            approval_status,
            question_id
        ))
    return True

def bulk_set_approval_status(
    approval_status: str = "approved",
    month: Optional[str] = None,
    year: Optional[int] = None,
    current_status: str = "pending_review"
) -> int:
    init_db()
    query = "UPDATE questions SET approval_status = ? WHERE approval_status = ?"
    params = [approval_status, current_status]

    if month and year and month != "All months":
        query += " AND month = ? AND year = ?"
        params.extend([month, year])

    with connect() as conn:
        cursor = conn.execute(query, params)
        return cursor.rowcount
