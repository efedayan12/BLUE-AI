"""
BLUE_AI — Response Formatter

LLM yanıtlarını kullanıcıya uygun formatta sunar.
Metin, sesli yanıt ve UI bileşenleri için format desteği.
"""

from __future__ import annotations

import re
from typing import Any


class ResponseFormatter:
    """Yanıt formatlayıcı."""

    @staticmethod
    def format_for_chat(response: str, response_type: str = "info") -> dict:
        """Chat penceresi için format."""
        return {
            "text": response,
            "type": response_type,
            "html": ResponseFormatter._to_html(response),
        }

    @staticmethod
    def format_for_voice(response: str) -> str:
        """Sesli yanıt için kısa/öz versiyon.

        Teknik detayları kaldırır, doğal konuşma diline çevirir.
        """
        # Emoji'leri kaldır
        text = re.sub(r'[^\w\s.,!?;:\-()/%]', '', response)

        # Çok satırlı listeyi sadeleştir (ilk 3 madde)
        lines = text.strip().split('\n')
        if len(lines) > 5:
            important_lines = [l for l in lines if l.strip() and not l.strip().startswith('  ')]
            text = '\n'.join(important_lines[:4])

        # Uzun teknik terimleri sadeleştir
        text = text.replace('bytes_sent', 'gönderilen').replace('bytes_recv', 'alınan')

        # 200 karaktere sınırla
        if len(text) > 200:
            text = text[:197] + "..."

        return text.strip()

    @staticmethod
    def format_system_status(data: dict) -> str:
        """Sistem durumunu güzel formatta göster."""
        cpu = data.get("cpu_percent", 0)
        ram = data.get("ram_percent", 0)
        disk = data.get("disk_percent", 0)

        # Renk/seviye
        def level(val):
            if val >= 90: return "🔴"
            if val >= 70: return "🟡"
            return "🟢"

        return (
            f"📊 Sistem Durumu\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{level(cpu)} CPU: %{cpu:.1f}\n"
            f"{level(ram)} RAM: %{ram:.1f} ({data.get('ram_used', '?')}/{data.get('ram_total', '?')})\n"
            f"{level(disk)} Disk: %{disk:.1f} (Boş: {data.get('disk_free', '?')})\n"
            f"⏱️ Uptime: {data.get('uptime', '?')}"
        )

    @staticmethod
    def _to_html(text: str) -> str:
        """Markdown benzeri metni basit HTML'e çevir."""
        if not text:
            return ""

        # Satırları işle
        lines = text.split('\n')
        html_lines = []
        in_code_block = False

        for line in lines:
            # Kod bloğu
            if line.strip().startswith('```'):
                if in_code_block:
                    html_lines.append('</code></pre>')
                    in_code_block = False
                else:
                    lang = line.strip()[3:] or ''
                    html_lines.append(f'<pre><code class="language-{lang}">')
                    in_code_block = True
                continue

            if in_code_block:
                html_lines.append(_escape_html(line))
                continue

            # Başlıklar
            if line.startswith('### '):
                html_lines.append(f'<h4>{_escape_html(line[4:])}</h4>')
            elif line.startswith('## '):
                html_lines.append(f'<h3>{_escape_html(line[3:])}</h3>')
            elif line.startswith('# '):
                html_lines.append(f'<h2>{_escape_html(line[2:])}</h2>')
            # Listeler
            elif line.strip().startswith('- ') or line.strip().startswith('• '):
                content = line.strip()[2:]
                html_lines.append(f'<div style="padding-left:1em">• {_escape_html(content)}</div>')
            elif re.match(r'^\d+\.\s', line.strip()):
                html_lines.append(f'<div style="padding-left:1em">{_escape_html(line.strip())}</div>')
            # Bold
            else:
                processed = line
                # **bold**
                processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', processed)
                # `code`
                processed = re.sub(r'`(.+?)`', r'<code style="background:rgba(255,255,255,0.1);padding:0.1em 0.3em;border-radius:3px">\1</code>', processed)
                html_lines.append(f'<div>{processed}</div>')

        return '\n'.join(html_lines)


def _escape_html(text: str) -> str:
    """HTML özel karakterlerini escape et."""
    return (
        text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
    )
