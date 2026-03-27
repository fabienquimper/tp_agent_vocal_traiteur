#!/usr/bin/env python3
"""
generate_penpot.py — Génère traiteur_dupont.penpot
Projet de design complet importable dans Penpot >= 2.0

Usage :
    python generate_penpot.py
    → Produit traiteur_dupont.penpot dans le dossier courant

Format : ZIP { manifest.json + [file-uuid].json }
Clés JSON : kebab-case (convention interne Penpot/Clojure)

Pages générées :
  1. Chat Mobile       — 390 × 844 px  (iPhone 14)
  2. Dashboard Desktop — 1280 × 800 px
  3. Design System     — 1440 × 960 px
"""

import json
import uuid
import zipfile
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
#  TOKENS DE DESIGN
# ══════════════════════════════════════════════════════════════════════════════

C = {
    "primary":      "#2E7D32",
    "primary_l":    "#4CAF50",
    "primary_bg":   "#E8F5E9",
    "accent":       "#FF8F00",
    "accent_bg":    "#FFF3E0",
    "pay_bg":       "#FFFDE7",
    "pay_border":   "#FFE082",
    "bg":           "#F5F5F0",
    "white":        "#FFFFFF",
    "text":         "#212121",
    "muted":        "#757575",
    "border":       "#EEEEEE",
    "gray_400":     "#BDBDBD",
    "error":        "#C62828",
    "error_bg":     "#FFEBEE",
    "online":       "#69F0AE",
    "blue":         "#1565C0",
    "blue_bg":      "#E3F2FD",
    "surface":      "#FAFAFA",
    "input_border": "#E0E0E0",
}


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS — primitives
# ══════════════════════════════════════════════════════════════════════════════

def uid() -> str:
    return str(uuid.uuid4())


def fill_color(hex_color: str, opacity: float = 1.0) -> dict:
    return {"fill-color": hex_color, "fill-opacity": opacity, "fill-type": "color"}


def stroke_solid(hex_color: str, width: float = 1.5) -> dict:
    return {
        "stroke-color": hex_color,
        "stroke-opacity": 1.0,
        "stroke-width": width,
        "stroke-style": "solid",
        "stroke-position": "inner",
        "stroke-type": "inner",
    }


def text_node(content: str, font_size: int = 14, font_weight: str = "400",
              color: str = "#212121", font_family: str = "Segoe UI",
              italic: bool = False) -> dict:
    """Nœud texte feuille pour le content d'un objet text."""
    return {
        "text": content,
        "font-family": font_family,
        "font-size": str(font_size),
        "font-weight": font_weight,
        "font-style": "italic" if italic else "normal",
        "letter-spacing": "0",
        "line-height": "1.5",
        "fills": [fill_color(color)],
    }


def text_content(content: str, font_size: int = 14, font_weight: str = "400",
                 color: str = "#212121", font_family: str = "Segoe UI",
                 italic: bool = False) -> dict:
    """Structure complète content pour un objet de type text."""
    return {
        "type": "root",
        "children": [{
            "type": "paragraph-set",
            "children": [{
                "type": "paragraph",
                "fills": [],
                "children": [text_node(content, font_size, font_weight,
                                       color, font_family, italic)],
            }],
        }],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS — constructeurs de formes
# ══════════════════════════════════════════════════════════════════════════════

def _base(shape_id: str, name: str, shape_type: str,
          x: float, y: float, w: float, h: float,
          parent_id: str, frame_id: str) -> dict:
    return {
        "id": shape_id,
        "name": name,
        "type": shape_type,
        "x": x, "y": y,
        "width": w, "height": h,
        "rotation": 0,
        "fills": [],
        "strokes": [],
        "opacity": 1,
        "blocked": False,
        "hidden": False,
        "parent-id": parent_id,
        "frame-id": frame_id,
    }


def mk_rect(name: str, x: float, y: float, w: float, h: float,
            fills=None, strokes=None, rx: float = 0,
            parent_id: str = "", frame_id: str = "") -> dict:
    s = _base(uid(), name, "rect", x, y, w, h, parent_id, frame_id)
    s["fills"] = fills or []
    s["strokes"] = strokes or []
    s["rx"] = rx
    s["ry"] = rx
    return s


def mk_circle(name: str, cx: float, cy: float, r: float,
              fills=None, parent_id: str = "", frame_id: str = "") -> dict:
    s = _base(uid(), name, "circle", cx - r, cy - r, r * 2, r * 2,
              parent_id, frame_id)
    s["fills"] = fills or []
    return s


def mk_text(name: str, x: float, y: float, w: float, h: float,
            txt: str, font_size: int = 14, font_weight: str = "400",
            color: str = "#212121", font_family: str = "Segoe UI",
            italic: bool = False,
            parent_id: str = "", frame_id: str = "") -> dict:
    s = _base(uid(), name, "text", x, y, w, h, parent_id, frame_id)
    s["content"] = text_content(txt, font_size, font_weight,
                                color, font_family, italic)
    s["grow-type"] = "fixed"
    return s


def mk_frame(name: str, x: float, y: float, w: float, h: float,
             fills=None, strokes=None, children_ids=None, clip: bool = True,
             parent_id: str = "", frame_id: str = "") -> dict:
    fid = uid()
    s = _base(fid, name, "frame", x, y, w, h, parent_id, frame_id)
    s["fills"] = fills or []
    s["strokes"] = strokes or []
    s["shapes"] = children_ids or []
    s["clip-content"] = clip
    return s


def mk_group(name: str, x: float, y: float, w: float, h: float,
             children_ids=None,
             parent_id: str = "", frame_id: str = "") -> dict:
    s = _base(uid(), name, "group", x, y, w, h, parent_id, frame_id)
    s["shapes"] = children_ids or []
    return s


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS — composition
# ══════════════════════════════════════════════════════════════════════════════

class Page:
    """Accumule les objets d'une page et maintient les relations parent/frame."""

    def __init__(self, page_id: str, page_name: str):
        self.id = page_id
        self.name = page_name
        self.objects: dict = {}

        # Root canvas (frame spécial Penpot — fond infini)
        self.root_id = uid()
        root = _base(self.root_id, "Page", "frame",
                     0, 0, 100_000, 100_000,
                     self.root_id, self.root_id)
        root["fills"] = [fill_color(C["bg"])]
        root["strokes"] = []
        root["shapes"] = []
        root["clip-content"] = False
        self.objects[self.root_id] = root

    # ── méthodes d'ajout ──────────────────────────────────────────────────────

    def add(self, shape: dict, parent_id: str, frame_id: str) -> str:
        """Enregistre la forme et retourne son id."""
        shape["parent-id"] = parent_id
        shape["frame-id"] = frame_id
        self.objects[shape["id"]] = shape
        # Ajoute l'enfant dans shapes du parent
        if "shapes" in self.objects.get(parent_id, {}):
            self.objects[parent_id]["shapes"].append(shape["id"])
        return shape["id"]

    def add_to_root(self, shape: dict) -> str:
        return self.add(shape, self.root_id, self.root_id)

    def export(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "objects": self.objects,
        }


def add_children(page: Page, parent_id: str, frame_id: str, shapes: list) -> list:
    """Ajoute une liste de formes au même parent/frame, retourne les ids."""
    ids = []
    for s in shapes:
        page.add(s, parent_id, frame_id)
        ids.append(s["id"])
    return ids


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — Chat Mobile (390 × 844)
# ══════════════════════════════════════════════════════════════════════════════

def build_chat_mobile() -> dict:
    page = Page(uid(), "Chat Mobile")
    proot = page.root_id

    # ── Artboard iPhone ───────────────────────────────────────────────────────
    ab = mk_frame("📱 iPhone 14 — Chat (390×844)",
                  120, 120, 390, 844,
                  fills=[fill_color(C["white"])])
    ab_id = ab["id"]
    page.add_to_root(ab)

    def ap(shape, pid=ab_id):
        """add to artboard"""
        page.add(shape, pid, ab_id)
        return shape["id"]

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = mk_frame("Header", 0, 0, 390, 64,
                   fills=[fill_color(C["primary"])])
    hdr_id = ap(hdr)

    def ah(shape):
        page.add(shape, hdr_id, ab_id)
        return shape["id"]

    ah(mk_rect("Header fond", 0, 0, 390, 64,
               fills=[fill_color(C["primary"])]))
    ah(mk_text("Logo", 20, 18, 32, 32, "🍽️", font_size=24,
               color=C["white"]))
    ah(mk_text("Titre", 60, 16, 240, 20, "Traiteur Dupont",
               font_size=17, font_weight="700", color=C["white"]))
    ah(mk_text("Sous-titre", 60, 38, 240, 16, "Assistant de commande",
               font_size=12, color=C["white"]))
    ah(mk_circle("Status dot online", 362, 28, 6,
                 fills=[fill_color(C["online"])]))
    ah(mk_text("Icône dashboard", 336, 40, 18, 18, "📋",
               font_size=14, color=C["white"]))
    ah(mk_text("Icône settings", 358, 40, 18, 18, "⚙",
               font_size=14, color=C["white"]))

    # ── Zone de chat ──────────────────────────────────────────────────────────
    chat_frame = mk_frame("Zone de chat", 0, 64, 390, 676,
                          fills=[fill_color(C["white"])])
    chat_id = ap(chat_frame)

    def ac(shape):
        page.add(shape, chat_id, ab_id)
        return shape["id"]

    # Message bot — Bienvenue
    g_w = mk_group("💬 Bot — Bienvenue", 16, 76, 318, 104)
    g_w_id = ac(g_w)

    def aw(s): page.add(s, g_w_id, ab_id); return s["id"]
    aw(mk_text("Avatar", 16, 82, 26, 26, "🤖", font_size=22))
    aw(mk_rect("Bulle bot", 46, 76, 260, 76,
               fills=[fill_color(C["primary_bg"])], rx=12))
    aw(mk_text("Texte bienvenue", 58, 84, 236, 68,
               "Bonjour ! Je suis l'assistant\nTraiteur Dupont. Que puis-je\nfaire pour vous ?",
               font_size=14))
    aw(mk_rect("Badge accueil bg", 46, 156, 66, 18,
               fills=[fill_color("#000000", 0.08)], rx=9))
    aw(mk_text("Badge accueil", 54, 159, 58, 14, "accueil",
               font_size=10, color=C["muted"]))

    # Message user — commande
    g_u = mk_group("💬 User — Commande", 108, 188, 266, 62)
    g_u_id = ac(g_u)

    def au(s): page.add(s, g_u_id, ab_id); return s["id"]
    au(mk_rect("Bulle user", 108, 188, 266, 44,
               fills=[fill_color(C["accent_bg"])], rx=12))
    au(mk_text("Texte commande", 120, 196, 242, 30,
               "Je voudrais un bœuf bourguignon",
               font_size=14))
    au(mk_rect("Badge commande bg", 262, 236, 112, 18,
               fills=[fill_color("#000000", 0.08)], rx=9))
    au(mk_text("Badge commande", 270, 239, 104, 14, "commande_simple",
               font_size=10, color=C["muted"]))

    # Message bot — confirmation + total
    g_c = mk_group("💬 Bot — Confirmation", 16, 264, 318, 120)
    g_c_id = ac(g_c)

    def aconf(s): page.add(s, g_c_id, ab_id); return s["id"]
    aconf(mk_text("Avatar", 16, 270, 26, 26, "🤖", font_size=22))
    aconf(mk_rect("Bulle bot confirmation", 46, 264, 300, 84,
                  fills=[fill_color(C["primary_bg"])], rx=12))
    aconf(mk_text("Texte confirmation", 58, 272, 276, 72,
                  "Parfait ! J'ai noté :\n• Bœuf bourguignon — 48,00 €\nPourriez-vous me donner votre\nnom et prénom ?",
                  font_size=14))
    aconf(mk_rect("Badge total fond", 46, 352, 116, 22,
                  fills=[fill_color(C["primary_bg"])],
                  strokes=[stroke_solid("#A5D6A7", 1)], rx=11))
    aconf(mk_text("Badge total texte", 58, 356, 104, 14, "Total : 48,00 €",
                  font_size=12, font_weight="600", color=C["primary"]))

    # Message user — nom
    g_n = mk_group("💬 User — Nom / Téléphone", 140, 386, 234, 44)
    g_n_id = ac(g_n)
    page.add(mk_rect("Bulle user nom", 140, 386, 234, 44,
                     fills=[fill_color(C["accent_bg"])], rx=12),
             g_n_id, ab_id)
    page.add(mk_text("Texte nom", 152, 394, 210, 30,
                     "Martin Sophie — 06 12 34 56 78",
                     font_size=14),
             g_n_id, ab_id)

    # Message bot — demande paiement
    g_p = mk_group("💬 Bot — Moyen de paiement ?", 16, 446, 318, 80)
    g_p_id = ac(g_p)
    page.add(mk_text("Avatar", 16, 452, 26, 26, "🤖", font_size=22),
             g_p_id, ab_id)
    page.add(mk_rect("Bulle bot paiement", 46, 446, 280, 64,
                     fills=[fill_color(C["primary_bg"])], rx=12),
             g_p_id, ab_id)
    page.add(mk_text("Texte paiement", 58, 454, 256, 50,
                     "Merci Sophie ! Quel est votre\nmoyen de paiement ?\n(CB ou paiement sur place)",
                     font_size=14),
             g_p_id, ab_id)

    # Formulaire CB
    g_form = mk_group("💳 Formulaire CB", 46, 540, 286, 166)
    g_form_id = ac(g_form)

    def aform(s): page.add(s, g_form_id, ab_id); return s["id"]
    aform(mk_rect("Formulaire fond", 46, 540, 286, 166,
                  fills=[fill_color(C["pay_bg"])],
                  strokes=[stroke_solid(C["pay_border"])], rx=12))
    aform(mk_text("Titre formulaire", 62, 556, 254, 20,
                  "💳 Paiement sécurisé",
                  font_size=14, font_weight="700"))
    aform(mk_text("Montant", 62, 576, 254, 16, "Montant : 48,00 €",
                  font_size=12, color=C["muted"]))
    aform(mk_rect("Champ numéro carte", 62, 596, 254, 34,
                  fills=[fill_color(C["white"])],
                  strokes=[stroke_solid(C["gray_400"])], rx=8))
    aform(mk_text("Placeholder carte", 74, 607, 230, 16,
                  "4242  4242  4242  4242",
                  font_size=13, color=C["gray_400"],
                  font_family="Consolas"))
    aform(mk_rect("Champ expiry", 62, 636, 120, 34,
                  fills=[fill_color(C["white"])],
                  strokes=[stroke_solid(C["gray_400"])], rx=8))
    aform(mk_text("Placeholder expiry", 74, 647, 100, 16, "MM/AA",
                  font_size=13, color=C["gray_400"], font_family="Consolas"))
    aform(mk_rect("Champ CVV", 196, 636, 120, 34,
                  fills=[fill_color(C["white"])],
                  strokes=[stroke_solid(C["gray_400"])], rx=8))
    aform(mk_text("Placeholder CVV", 208, 647, 100, 16, "CVV",
                  font_size=13, color=C["gray_400"], font_family="Consolas"))
    aform(mk_rect("Bouton payer fond", 62, 676, 254, 22,
                  fills=[fill_color(C["primary"])], rx=11))
    aform(mk_text("Bouton payer texte", 62, 678, 254, 18,
                  "Payer 48,00 €",
                  font_size=13, font_weight="700", color=C["white"]))

    # Barre de statut
    ap(mk_rect("Barre de statut", 0, 740, 390, 28,
               fills=[fill_color(C["surface"])],
               strokes=[stroke_solid(C["border"], 1)]))
    ap(mk_text("Statut texte", 16, 750, 300, 14,
               "✅ Service en ligne — Agent prêt",
               font_size=11, color=C["muted"]))

    # Zone de saisie
    inp_frame = mk_frame("Zone de saisie", 0, 768, 390, 76,
                         fills=[fill_color(C["white"])])
    inp_id = ap(inp_frame)

    def ainp(s): page.add(s, inp_id, ab_id); return s["id"]
    ainp(mk_rect("Champ texte", 12, 780, 326, 40,
                 fills=[fill_color(C["white"])],
                 strokes=[stroke_solid(C["gray_400"])], rx=20))
    ainp(mk_text("Placeholder message", 28, 793, 280, 16, "Votre message...",
                 font_size=14, color=C["gray_400"]))
    ainp(mk_rect("Bouton envoyer", 344, 780, 40, 40,
                 fills=[fill_color(C["primary"])], rx=20))
    ainp(mk_text("Icône envoyer", 356, 792, 20, 16, "▶",
                 font_size=14, color=C["white"]))
    ainp(mk_rect("Bouton micro fond", 12, 826, 366, 12,
                 fills=[fill_color("#F5F5F5")],
                 strokes=[stroke_solid(C["input_border"])], rx=6))
    ainp(mk_text("Micro label", 120, 827, 150, 12, "🎤  Maintenir pour parler",
                 font_size=10, color=C["muted"]))

    return page.export()


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — Dashboard Desktop (1280 × 800)
# ══════════════════════════════════════════════════════════════════════════════

def build_dashboard_desktop() -> dict:
    page = Page(uid(), "Dashboard Desktop")
    proot = page.root_id

    ab = mk_frame("🖥️ Dashboard Traiteur (1280×800)",
                  80, 80, 1280, 800,
                  fills=[fill_color(C["bg"])])
    ab_id = ab["id"]
    page.add_to_root(ab)

    def ap(s): page.add(s, ab_id, ab_id); return s["id"]

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = mk_frame("Header", 0, 0, 1280, 64,
                   fills=[fill_color(C["primary"])])
    hdr_id = ap(hdr)

    def ah(s): page.add(s, hdr_id, ab_id); return s["id"]
    ah(mk_text("Logo", 24, 18, 30, 30, "🍽️", font_size=24, color=C["white"]))
    ah(mk_text("Titre", 60, 16, 300, 20, "Traiteur Dupont",
               font_size=18, font_weight="700", color=C["white"]))
    ah(mk_text("Sous-titre", 60, 38, 300, 16, "Tableau de bord — Commandes",
               font_size=12, color=C["white"]))
    ah(mk_text("Nav chat", 1090, 30, 120, 18, "💬 Interface client",
               font_size=13, color=C["white"]))
    ah(mk_text("Nav dashboard", 1210, 30, 80, 18, "📋 Dashboard",
               font_size=13, font_weight="700", color=C["white"]))
    ah(mk_circle("Status dot", 1264, 50, 5,
                 fills=[fill_color(C["online"])]))
    ah(mk_text("Status label", 1150, 54, 110, 14, "Service en ligne",
               font_size=11, color=C["white"]))

    # ── Titre de page ─────────────────────────────────────────────────────────
    ap(mk_text("Titre page", 40, 84, 400, 28, "Commandes du jour",
               font_size=22, font_weight="700"))
    ap(mk_text("Sous-titre page", 40, 114, 400, 16,
               "Mise à jour automatique toutes les 30 secondes",
               font_size=13, color=C["muted"]))

    # ── Cartes stats ──────────────────────────────────────────────────────────
    def stat_card(name, x, color_bar, label, value, unit=""):
        g = mk_group(f"Carte — {name}", x, 142, 270, 100)
        g_id = ap(g)
        page.add(mk_rect("Fond carte", x, 142, 270, 100,
                         fills=[fill_color(C["white"])],
                         strokes=[stroke_solid(C["border"], 1)], rx=12),
                 g_id, ab_id)
        page.add(mk_rect("Barre couleur", x, 142, 6, 100,
                         fills=[fill_color(color_bar)], rx=3),
                 g_id, ab_id)
        page.add(mk_text("Label", x + 26, 162, 220, 14, label,
                         font_size=12, font_weight="600", color=C["muted"]),
                 g_id, ab_id)
        page.add(mk_text("Valeur", x + 26, 194, 120, 40, value,
                         font_size=36, font_weight="700", color=color_bar),
                 g_id, ab_id)
        if unit:
            page.add(mk_text("Unité", x + 26 + len(value) * 22, 210, 120, 20,
                             unit, font_size=13, color=C["muted"]),
                     g_id, ab_id)

    stat_card("Total commandes", 40,  C["primary"], "COMMANDES TOTALES", "12", "commandes")
    stat_card("CB payées",        330, C["blue"],    "PAYÉES PAR CB",      "8",  "validées")
    stat_card("Sur place",        620, C["accent"],  "PAIEMENT SUR PLACE", "3",  "à régler")

    # Carte CA (plus large)
    g_ca = mk_group("Carte — CA", 910, 142, 330, 100)
    g_ca_id = ap(g_ca)
    page.add(mk_rect("Fond CA", 910, 142, 330, 100,
                     fills=[fill_color(C["white"])],
                     strokes=[stroke_solid(C["border"], 1)], rx=12),
             g_ca_id, ab_id)
    page.add(mk_rect("Barre CA", 910, 142, 6, 100,
                     fills=[fill_color(C["primary"])], rx=3),
             g_ca_id, ab_id)
    page.add(mk_text("Label CA", 936, 162, 280, 14, "CHIFFRE D'AFFAIRES",
                     font_size=12, font_weight="600", color=C["muted"]),
             g_ca_id, ab_id)
    page.add(mk_text("Valeur CA", 936, 194, 280, 40, "1 248 €",
                     font_size=36, font_weight="700", color=C["primary"]),
             g_ca_id, ab_id)

    # ── Tableau des commandes ─────────────────────────────────────────────────
    tbl = mk_frame("Tableau des commandes", 40, 262, 1200, 500,
                   fills=[fill_color(C["white"])],
                   strokes=[stroke_solid(C["border"], 1)])
    tbl_id = ap(tbl)

    def at(s): page.add(s, tbl_id, ab_id); return s["id"]

    # En-tête tableau
    at(mk_rect("En-tête fond", 40, 262, 1200, 44,
               fills=[fill_color(C["bg"])]))
    at(mk_rect("Séparateur en-tête", 40, 305, 1200, 1,
               fills=[fill_color(C["border"])]))

    headers = [
        ("RÉF.",       64),  ("HEURE",  140), ("CLIENT",      220),
        ("TÉLÉPHONE", 400),  ("ARTICLES", 530), ("TOTAL",     820),
        ("PAIEMENT",  920),  ("STATUT", 1080),
    ]
    for label, x in headers:
        at(mk_text(f"Col {label}", x, 275, 100, 14, label,
                   font_size=12, font_weight="700", color=C["text"]))

    # Données — 5 lignes
    rows = [
        ("A1B2C3", "14:32", "Martin Sophie",  "06 12 34 56 78", "Bœuf bourguignon ×1",         "48,00 €",  "💳 CB payé",      C["blue_bg"],    C["blue"],    "✅ Confirmée",  C["primary_bg"], C["primary"]),
        ("D4E5F6", "13:15", "Dubois Pierre",  "07 98 76 54 32", "Poulet rôti ×2, Tarte ×1",    "104,00 €", "🏪 Sur place",    C["accent_bg"],  C["accent"],  "⏳ En attente", C["accent_bg"],  C["accent"]),
        ("G7H8I9", "12:48", "Bernard Lucas",  "06 55 44 33 22", "Plateau fromages ×1",          "35,00 €",  "❌ CB refusée",   C["error_bg"],   C["error"],   "⏳ En attente", C["accent_bg"],  C["accent"]),
        ("J1K2L3", "12:05", "Moreau Claire",  "06 11 22 33 44", "Quiche lorraine ×3, Salade ×2","87,00 €",  "💳 CB payé",      C["blue_bg"],    C["blue"],    "✅ Confirmée",  C["primary_bg"], C["primary"]),
        ("M4N5O6", "11:30", "Petit Thomas",   "07 22 33 44 55", "Tarte aux pommes ×2",          "40,00 €",  "⌛ En attente CB", C["primary_bg"], C["primary"], "🔄 En cours",   C["blue_bg"],    C["blue"]),
    ]

    for i, (ref, heure, client, tel, articles, total,
            badge_pay, badge_pay_bg, badge_pay_fg,
            badge_st, badge_st_bg, badge_st_fg) in enumerate(rows):
        y_base = 314 + i * 42
        at(mk_rect(f"Séparateur {i}", 40, y_base, 1200, 1,
                   fills=[fill_color(C["border"])]))
        y = y_base + 24
        at(mk_text(f"Ref {i}", 64, y_base + 6, 66, 30, ref,
                   font_size=12, color=C["muted"], font_family="Consolas"))
        at(mk_text(f"Heure {i}",   140, y_base + 6, 70, 30, heure,   font_size=13))
        at(mk_text(f"Client {i}",  220, y_base + 6, 170, 30, client,  font_size=13))
        at(mk_text(f"Tel {i}",     400, y_base + 6, 120, 30, tel,     font_size=13))
        at(mk_text(f"Articles {i}", 530, y_base + 6, 280, 30, articles, font_size=12))
        at(mk_text(f"Total {i}",   820, y_base + 6, 90, 30, total,
                   font_size=13, font_weight="600"))
        # Badge paiement
        at(mk_rect(f"Badge pay fond {i}", 916, y_base + 8, 110, 22,
                   fills=[fill_color(badge_pay_bg)], rx=11))
        at(mk_text(f"Badge pay texte {i}", 924, y_base + 11, 98, 14,
                   badge_pay, font_size=11, font_weight="600", color=badge_pay_fg))
        # Badge statut
        at(mk_rect(f"Badge st fond {i}", 1076, y_base + 8, 100, 22,
                   fills=[fill_color(badge_st_bg)], rx=11))
        at(mk_text(f"Badge st texte {i}", 1084, y_base + 11, 88, 14,
                   badge_st, font_size=11, font_weight="600", color=badge_st_fg))

    at(mk_text("Ellipsis", 580, 532, 200, 20, "• • •  7 autres commandes",
               font_size=14, color=C["gray_400"]))

    # Footer tableau
    at(mk_rect("Footer séparateur", 40, 726, 1200, 1,
               fills=[fill_color(C["border"])]))
    at(mk_text("Footer info", 64, 742, 300, 16,
               "Affichage de 5 / 12 commandes",
               font_size=12, color=C["muted"]))
    at(mk_text("Export Excel", 1080, 742, 160, 16, "↓ Exporter en Excel",
               font_size=12, font_weight="600", color=C["primary"]))

    return page.export()


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — Design System (1440 × 960)
# ══════════════════════════════════════════════════════════════════════════════

def build_design_system() -> dict:
    page = Page(uid(), "Design System")

    ab = mk_frame("🎨 Design System — Traiteur Dupont (1440×960)",
                  60, 60, 1440, 960,
                  fills=[fill_color(C["bg"])])
    ab_id = ab["id"]
    page.add_to_root(ab)

    def ap(s): page.add(s, ab_id, ab_id); return s["id"]

    # ── Titre page ────────────────────────────────────────────────────────────
    ap(mk_text("Titre DS", 40, 40, 700, 36,
               "Design System — Traiteur Dupont",
               font_size=28, font_weight="700"))
    ap(mk_text("Sous-titre DS", 40, 78, 600, 20,
               "Tokens, composants et typographie · v1.0",
               font_size=14, color=C["muted"]))
    ap(mk_rect("Séparateur titre", 40, 96, 1360, 2,
               fills=[fill_color(C["border"])]))

    # ══ SECTION 1 — COULEURS ══════════════════════════════════════════════════
    ap(mk_text("Titre couleurs", 40, 116, 300, 24,
               "01 — Palette de couleurs",
               font_size=18, font_weight="700"))

    def color_swatch(name, x, hex_color, label, star=False,
                     light_bg=False):
        g = mk_group(f"Swatch — {name}", x, 140, 68, 100)
        g_id = ap(g)
        border = [stroke_solid(C["border"], 1)] if light_bg else []
        page.add(mk_rect("Swatch carré", x, 140, 60, 60,
                         fills=[fill_color(hex_color)],
                         strokes=border, rx=8),
                 g_id, ab_id)
        lbl_color = hex_color if star else C["muted"]
        page.add(mk_text("Swatch label", x, 206,
                         80, 14,
                         ("★ " if star else "") + label,
                         font_size=10, font_weight="700" if star else "400",
                         color=lbl_color),
                 g_id, ab_id)
        page.add(mk_text("Swatch hex", x, 220, 80, 14, hex_color,
                         font_size=10, color=C["muted"],
                         font_family="Consolas"),
                 g_id, ab_id)

    # Verts
    ap(mk_text("Label verts", 40, 130, 200, 14, "VERT PRIMAIRE",
               font_size=11, font_weight="600", color=C["muted"]))
    color_swatch("primary-900", 40,  "#1B5E20", "900")
    color_swatch("primary-700", 112, C["primary"], "700", star=True)
    color_swatch("primary-500", 184, "#388E3C", "500")
    color_swatch("primary-300", 256, C["primary_l"], "300")
    color_swatch("primary-100", 328, C["primary_bg"], "100", light_bg=True)

    # Oranges
    ap(mk_text("Label oranges", 430, 130, 200, 14, "ORANGE ACCENT",
               font_size=11, font_weight="600", color=C["muted"]))
    color_swatch("accent-900", 430, "#E65100", "900")
    color_swatch("accent-700", 502, C["accent"], "700", star=True)
    color_swatch("accent-100", 574, C["accent_bg"], "100", light_bg=True)

    # Neutres
    ap(mk_text("Label neutres", 672, 130, 200, 14, "NEUTRES",
               font_size=11, font_weight="600", color=C["muted"]))
    color_swatch("gray-900", 672,  "#212121", "900")
    color_swatch("gray-700", 744,  "#424242", "700")
    color_swatch("gray-600", 816,  "#757575", "600")
    color_swatch("gray-400", 888,  C["gray_400"], "400")
    color_swatch("gray-200", 960,  C["border"], "200", light_bg=True)
    color_swatch("gray-50",  1032, C["bg"], "50", light_bg=True)
    color_swatch("white",    1104, C["white"], "white", light_bg=True)

    # Sémantiques
    ap(mk_text("Label séman.", 1192, 130, 200, 14, "SÉMANTIQUES",
               font_size=11, font_weight="600", color=C["muted"]))
    color_swatch("error",    1192, C["error"], "error")
    color_swatch("error-bg", 1264, C["error_bg"], "error-bg", light_bg=True)
    color_swatch("info",     1336, C["blue"], "info")

    ap(mk_rect("Séparateur couleurs", 40, 248, 1360, 1.5,
               fills=[fill_color(C["border"])]))

    # ══ SECTION 2 — TYPOGRAPHIE ═══════════════════════════════════════════════
    ap(mk_text("Titre typo", 40, 268, 300, 24,
               "02 — Typographie",
               font_size=18, font_weight="700"))
    ap(mk_text("Sous-titre typo", 40, 292, 400, 16,
               "Police : Segoe UI / system-ui · Grille 8px",
               font_size=12, color=C["muted"]))

    # Échelle de taille
    type_scale = [
        ("3xl · 32px · Bold", "Titre principal",      32, "700"),
        ("2xl · 24px · Bold", "Métrique dashboard",   24, "700"),
        ("xl · 18px · Bold",  "Titre de section",     18, "700"),
        ("lg · 16px · Regular", "Corps large mobile", 16, "400"),
        ("md · 14px · Regular", "Corps standard — texte courant dans les bulles", 14, "400"),
        ("sm · 12px · Regular", "Label, badge, horodatage", 12, "400"),
        ("xs · 11px · Regular", "Micro label",        11, "400"),
    ]
    y = 316
    for token, sample, size, weight in type_scale:
        ap(mk_text(f"Sample {token}", 40, y, 700, size + 8, sample,
                   font_size=size, font_weight=weight))
        ap(mk_text(f"Token {token}", 40, y + size + 4, 300, 14, token,
                   font_size=11, color=C["muted"]))
        y += size + 26

    # Colonne graisses
    ap(mk_rect("Sépar. col typo", 720, 268, 1.5, 360,
               fills=[fill_color(C["border"])]))
    ap(mk_text("Label graisses", 740, 290, 200, 14, "GRAISSES",
               font_size=11, font_weight="600", color=C["muted"]))
    weights = [("400 · Regular", "400"), ("500 · Medium", "500"),
               ("600 · Semibold", "600"), ("700 · Bold", "700")]
    for i, (label, w) in enumerate(weights):
        ap(mk_text(f"Weight {w}", 740, 316 + i * 52, 300, 24, label,
                   font_size=18, font_weight=w))
        ap(mk_text(f"Weight usage {w}", 740, 340 + i * 52, 300, 14,
                   {
                       "400": "Corps, labels, placeholder",
                       "500": "Sous-titres importants",
                       "600": "Boutons, badges, totaux",
                       "700": "Titres, CTA principaux",
                   }[w], font_size=11, color=C["muted"]))

    # Monospace
    ap(mk_text("Label mono", 740, 530, 200, 14, "MONOSPACE",
               font_size=11, font_weight="600", color=C["muted"]))
    ap(mk_text("Sample mono carte", 740, 550, 500, 24,
               "4242  4242  4242  4242",
               font_size=16, font_family="Consolas"))
    ap(mk_text("Sample mono ref", 740, 578, 400, 18,
               "Réf. A1B2C3D4  ·  14h32",
               font_size=13, color=C["muted"], font_family="Consolas"))

    ap(mk_rect("Séparateur typo", 40, 638, 1360, 1.5,
               fills=[fill_color(C["border"])]))

    # ══ SECTION 3 — COMPOSANTS ═══════════════════════════════════════════════
    ap(mk_text("Titre compo", 40, 654, 400, 24,
               "03 — Composants — Atomes",
               font_size=18, font_weight="700"))

    # Boutons
    def btn(name, x, label, bg, text_color=C["white"],
            border_color=None, rx=22):
        g = mk_group(f"Btn {name}", x, 684, 160, 44)
        g_id = ap(g)
        strokes = [stroke_solid(border_color)] if border_color else []
        page.add(mk_rect(f"Btn fond {name}", x, 684, 160, 44,
                         fills=[fill_color(bg)],
                         strokes=strokes, rx=rx),
                 g_id, ab_id)
        page.add(mk_text(f"Btn label {name}", x, 695, 160, 22, label,
                         font_size=14, font_weight="700", color=text_color),
                 g_id, ab_id)

    ap(mk_text("Label btns", 40, 672, 100, 14, "BOUTONS",
               font_size=11, font_weight="600", color=C["muted"]))
    btn("Primaire",    40,  "Envoyer ▶",     C["primary"])
    btn("Payer",       210, "Payer 48,00 €", C["primary"])
    btn("Sur place",   380, "Sur place 🏪",  C["accent"])
    btn("Désactivé",   550, "Désactivé",     C["gray_400"])
    btn("Annuler",     720, "Annuler",       C["white"],
        text_color=C["muted"], border_color=C["gray_400"])

    # Input champ
    ap(mk_text("Label inputs", 900, 672, 100, 14, "INPUTS",
               font_size=11, font_weight="600", color=C["muted"]))
    ap(mk_rect("Input normal", 900, 684, 240, 44,
               fills=[fill_color(C["white"])],
               strokes=[stroke_solid(C["gray_400"])], rx=22))
    ap(mk_text("Input placeholder", 920, 696, 200, 18,
               "Votre message...", font_size=14, color=C["gray_400"]))
    ap(mk_rect("Input focus", 1156, 684, 240, 44,
               fills=[fill_color(C["white"])],
               strokes=[stroke_solid(C["primary"], 2)], rx=22))
    ap(mk_text("Input focus label", 1160, 672, 100, 14, "FOCUS",
               font_size=11, font_weight="600", color=C["primary"]))
    ap(mk_text("Input focus text", 1176, 696, 210, 18,
               "Je voudrais...", font_size=14))

    # Badges intent
    ap(mk_text("Label badges", 40, 746, 100, 14, "BADGES INTENT",
               font_size=11, font_weight="600", color=C["muted"]))
    badges_intent = [
        ("accueil", 40, 76, "#000000", 0.08),
        ("commande_simple", 132, 120, "#000000", 0.08),
        ("catalogue", 268, 68, "#000000", 0.08),
        ("horaires", 350, 64, "#000000", 0.08),
        ("paiement", 428, 70, "#000000", 0.08),
    ]
    for label, x, w, bg, op in badges_intent:
        g = mk_group(f"Badge intent {label}", x, 762, w, 22)
        g_id = ap(g)
        page.add(mk_rect(f"Badge bg {label}", x, 762, w, 22,
                         fills=[fill_color(bg, op)], rx=11),
                 g_id, ab_id)
        page.add(mk_text(f"Badge t {label}", x + 10, 765, w - 20, 14,
                         label, font_size=10, color=C["muted"]),
                 g_id, ab_id)

    # Badges paiement
    ap(mk_text("Label badges pay", 520, 746, 180, 14, "BADGES PAIEMENT",
               font_size=11, font_weight="600", color=C["muted"]))
    badges_pay = [
        ("💳 CB payé",      520, 90, C["blue_bg"],   C["blue"]),
        ("🏪 Sur place",    624, 98, C["accent_bg"],  C["accent"]),
        ("❌ CB refusée",   736, 100, C["error_bg"],  C["error"]),
        ("⌛ En attente CB", 850, 112, C["primary_bg"], C["primary"]),
    ]
    for label, x, w, bg, fg in badges_pay:
        g = mk_group(f"Badge pay {label}", x, 762, w, 22)
        g_id = ap(g)
        page.add(mk_rect(f"Badge bg", x, 762, w, 22,
                         fills=[fill_color(bg)], rx=11),
                 g_id, ab_id)
        page.add(mk_text(f"Badge t", x + 8, 765, w - 12, 14,
                         label, font_size=11, font_weight="600", color=fg),
                 g_id, ab_id)

    # Tokens d'espacement
    ap(mk_text("Label spacing", 40, 810, 200, 14, "ESPACEMENTS (grille 8px)",
               font_size=11, font_weight="600", color=C["muted"]))
    spacings = [(4, 40), (8, 76), (12, 120), (16, 168), (20, 220),
                (24, 274), (32, 334), (40, 402), (48, 478)]
    for sp, x in spacings:
        ap(mk_rect(f"Spacing {sp}px", x, 828, sp, 16,
                   fills=[fill_color(C["primary"])], rx=2))
        ap(mk_text(f"Spacing label {sp}", x, 850, sp + 20, 14,
                   f"{sp}px", font_size=10, color=C["muted"]))

    # Rayons
    ap(mk_text("Label radius", 580, 810, 200, 14, "RAYONS",
               font_size=11, font_weight="600", color=C["muted"]))
    radii = [(4, 580), (8, 646), (12, 720), (16, 800), (22, 890)]
    for rx, x in radii:
        ap(mk_rect(f"Radius {rx}", x, 824, 48, 28,
                   fills=[],
                   strokes=[stroke_solid(C["primary"])], rx=rx))
        ap(mk_text(f"Radius label {rx}", x, 858, 60, 14,
                   f"{rx}px", font_size=10, color=C["muted"]))

    # Pill radius
    ap(mk_rect("Radius pill", 980, 824, 80, 28,
               fills=[], strokes=[stroke_solid(C["primary"])], rx=99))
    ap(mk_text("Radius pill label", 980, 858, 80, 14,
               "pill", font_size=10, color=C["muted"]))

    # Footer
    ap(mk_rect("Footer sep", 40, 912, 1360, 1.5,
               fills=[fill_color(C["border"])]))
    ap(mk_text("Footer", 40, 928, 800, 16,
               "Traiteur Dupont — Design System v1.0 · WCAG 2.1 AA · Grille 8px · Police système",
               font_size=12, color=C["muted"]))
    ap(mk_text("Footer droit", 1280, 928, 120, 16, "etape_00a · Penpot",
               font_size=12, color=C["muted"]))

    return page.export()


# ══════════════════════════════════════════════════════════════════════════════
#  ASSEMBLAGE DU FICHIER .penpot
# ══════════════════════════════════════════════════════════════════════════════

def build_penpot_file() -> bytes:
    file_id = uid()

    page_chat      = build_chat_mobile()
    page_dashboard = build_dashboard_desktop()
    page_ds        = build_design_system()

    pages_order = [page_chat["id"], page_dashboard["id"], page_ds["id"]]
    pages_index = {
        page_chat["id"]:      page_chat,
        page_dashboard["id"]: page_dashboard,
        page_ds["id"]:        page_ds,
    }

    # ── manifest.json ─────────────────────────────────────────────────────────
    manifest = {
        "version": 2,
        "files": [{"id": file_id, "name": "Traiteur Dupont"}],
    }

    # ── [file-id].json ────────────────────────────────────────────────────────
    file_data = {
        "id":           file_id,
        "name":         "Traiteur Dupont",
        "revn":         0,
        "pages":        pages_order,
        "pagesIndex":   pages_index,
        "components":   {},
        "colors":       {
            # Styles partagés — directement utilisables dans Penpot
            uid(): {"name": "Vert / Primaire 700",  "color": C["primary"],    "opacity": 1},
            uid(): {"name": "Vert / Primaire BG",   "color": C["primary_bg"], "opacity": 1},
            uid(): {"name": "Orange / Accent 700",  "color": C["accent"],     "opacity": 1},
            uid(): {"name": "Orange / Accent BG",   "color": C["accent_bg"],  "opacity": 1},
            uid(): {"name": "Erreur",                "color": C["error"],      "opacity": 1},
            uid(): {"name": "Texte principal",       "color": C["text"],       "opacity": 1},
            uid(): {"name": "Texte secondaire",      "color": C["muted"],      "opacity": 1},
            uid(): {"name": "Paiement fond",         "color": C["pay_bg"],     "opacity": 1},
        },
        "typographies": {
            uid(): {
                "name": "Segoe UI / Regular",
                "font-family": "Segoe UI",
                "font-style": "normal",
                "font-size": "14",
                "font-weight": "400",
                "letter-spacing": "0",
                "line-height": "1.5",
            },
            uid(): {
                "name": "Segoe UI / Bold",
                "font-family": "Segoe UI",
                "font-style": "normal",
                "font-size": "14",
                "font-weight": "700",
                "letter-spacing": "0",
                "line-height": "1.5",
            },
            uid(): {
                "name": "Mono / Code",
                "font-family": "Consolas",
                "font-style": "normal",
                "font-size": "13",
                "font-weight": "400",
                "letter-spacing": "0",
                "line-height": "1.5",
            },
        },
        "media": {},
    }

    # ── Empaquetage ZIP ───────────────────────────────────────────────────────
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(f"{file_id}.json",
                    json.dumps(file_data, ensure_ascii=False, indent=2))
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    output = Path(__file__).parent / "traiteur_dupont.penpot"
    data = build_penpot_file()
    output.write_bytes(data)

    print(f"✅  Fichier généré : {output}")
    print(f"    Taille         : {len(data) / 1024:.1f} Ko")
    print()
    print("Comment importer dans Penpot :")
    print("  1. Ouvre Penpot → ton espace de travail")
    print("  2. Menu principal (☰) → 'Import Penpot file'")
    print("  3. Sélectionne traiteur_dupont.penpot")
    print("  4. Le projet apparaît avec 3 pages nommées et tous les calques")
    print()
    print("Pages générées :")
    print("  📱 Chat Mobile       — 390 × 844 px")
    print("  🖥️  Dashboard Desktop — 1280 × 800 px")
    print("  🎨 Design System     — 1440 × 960 px")
