"""Build the paper PDF from PAPER_WRITING.md, following the sprint template."""
import html
import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle,
    KeepTogether, HRFlowable,
)

BASE = Path(__file__).resolve().parent
OUT = BASE / 'output/pdf/Honor_Among_Agents.pdf'
FONT = Path('/System/Library/Fonts/Supplemental')
for name, filename in [('Paper','Times New Roman.ttf'),('Paper-Bold','Times New Roman Bold.ttf'),
                       ('Paper-Italic','Times New Roman Italic.ttf'),('Paper-BoldItalic','Times New Roman Bold Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/filename)))
pdfmetrics.registerFontFamily('Paper',normal='Paper',bold='Paper-Bold',italic='Paper-Italic',boldItalic='Paper-BoldItalic')

INK = colors.HexColor('#141414')
LINK = '#174c73'
STYLES = {
    'body': ParagraphStyle('body',fontName='Paper',fontSize=10.5,leading=12.4,
        spaceAfter=4,textColor=INK,allowWidows=0,allowOrphans=0),
    'h1': ParagraphStyle('h1',fontName='Paper-Bold',fontSize=14,leading=17,
        spaceBefore=7,spaceAfter=8,keepWithNext=True,textColor=INK),
    'h2': ParagraphStyle('h2',fontName='Paper-Bold',fontSize=11.5,leading=14,
        spaceBefore=8,spaceAfter=5,keepWithNext=True,textColor=INK),
    'caption': ParagraphStyle('caption',fontName='Paper',fontSize=9.1,leading=11,
        spaceBefore=4,spaceAfter=8,textColor=INK),
    'cell': ParagraphStyle('cell',fontName='Paper',fontSize=9.2,leading=11,textColor=INK),
    'reference': ParagraphStyle('reference',fontName='Paper',fontSize=10.5,leading=13,
        spaceAfter=12,leftIndent=12,firstLineIndent=-12,textColor=INK),
    'abstract': ParagraphStyle('abstract',fontName='Paper',fontSize=11,leading=13.6,
        leftIndent=36,rightIndent=36,spaceAfter=8,textColor=INK,allowWidows=0,allowOrphans=0),
}

def inline(s):
    # Escape prose first; then translate the small Markdown subset used here.
    s=html.escape(s,quote=False)
    s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:f'<a href="{html.escape(html.unescape(m[2]),quote=True)}" color="{LINK}">{m[1]}</a>',s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<i>\1</i>',s)
    s=re.sub(r'10\^(-?\d+)',r'10<super>\1</super>',s)
    return s

def para(s,style='body'):
    return Paragraph(inline(s),STYLES[style])

class PaperDoc(SimpleDocTemplate):
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name in ('h1','h2'):
            title=flowable.getPlainText()
            self.locations[title]=self.page
            if flowable.style.name=='h1':
                key='section-'+str(len(self.locations))
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(title,key,level=0,closed=False)

def furniture(canvas,doc):
    canvas.saveState()
    canvas.setTitle('Honor Among Agents')
    canvas.setAuthor('Sarosh Thalappil')
    canvas.setSubject('Trust, promise-keeping, and shared resources in LLM agent groups')
    canvas.setFont('Paper',9)
    canvas.setFillColor(colors.HexColor('#555555'))
    canvas.drawCentredString(306,34,str(doc.page))
    if doc.page==1:
        canvas.setStrokeColor(colors.black);canvas.setLineWidth(.5)
        canvas.line(72,72,205,72)
        canvas.setFont('Paper',8)
        canvas.drawString(72,58,'Research conducted at the Swarm Alignment Hackathon, November 2026.')
    else:
        canvas.setFont('Paper',8.5)
        canvas.drawString(72,754,'Honor Among Agents')
        canvas.drawRightString(540,754,'Sarosh Thalappil')
    canvas.restoreState()

def make_table(lines):
    cells=[[c.strip() for c in line.strip().strip('|').split('|')] for line in lines]
    headings=cells[0]
    cells=[headings]+cells[2:]
    n=len(headings)
    if headings[0]=='Model' and n==5:
        widths=[138,83,73,84,90] if 'Winning pools' in headings else [138,61,86,85,98]
    elif headings[0]=='Condition':
        widths=[168,300]
    else:
        widths=[192,69,69,69,69]
    rows=[]
    for i,row in enumerate(cells):
        rows.append([Paragraph(('<b>'+inline(c)+'</b>') if i==0 else inline(c),STYLES['cell']) for c in row])
    t=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),
        ('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),
        ('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LINEABOVE',(0,0),(-1,0),.7,colors.black),
        ('LINEBELOW',(0,0),(-1,0),.5,colors.black),
        ('LINEBELOW',(0,-1),(-1,-1),.7,colors.black),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f5f5')]),
    ]))
    return t

def build():
    source=(BASE/'PAPER_WRITING.md').read_text()
    cover,rest=source.split('<!-- pagebreak -->',1)
    abstract=cover.split('# Abstract',1)[1].strip()
    assert 150<=len(abstract.split())<=250
    title_style=ParagraphStyle('title',fontName='Paper-Bold',fontSize=23,leading=28,alignment=TA_CENTER)
    author_style=ParagraphStyle('author',fontName='Paper',fontSize=11,leading=15,alignment=TA_CENTER)
    abstract_heading=ParagraphStyle('abstract-heading',fontName='Paper-Bold',fontSize=14,leading=18,alignment=TA_CENTER)
    story=[Spacer(1,13),HRFlowable(width='100%',thickness=2.3,color=colors.black),Spacer(1,22),
        Paragraph('Honor Among Agents',title_style),Spacer(1,25),
        Paragraph('<b>Sarosh Thalappil</b><br/>Independent<br/><a href="mailto:saroshcodes@gmail.com" color="#141414">saroshcodes@gmail.com</a>',author_style),
        Spacer(1,17),Paragraph('<b>With</b><br/>Apart Research',author_style),Spacer(1,23),
        Paragraph('Abstract',abstract_heading),Spacer(1,12)]
    story += [para(p,'abstract') for p in abstract.split('\n\n')]
    story += [PageBreak()]
    lines=rest.splitlines();i=0;in_refs=False
    while i<len(lines):
        line=lines[i].strip()
        if not line:
            i+=1;continue
        if line=='<!-- pagebreak -->':
            story.append(PageBreak());i+=1;continue
        if line.startswith('# '):
            text=line[2:];in_refs=text=='References'
            story.append(para(text,'h1'));i+=1;continue
        if line.startswith('## '):
            story.append(para(line[3:],'h2'));i+=1;continue
        if line.startswith('!['):
            m=re.fullmatch(r'!\[([^]]*)\]\(([^)]+)\)',line)
            path=BASE/m[2]
            img=Image(str(path))
            width=468
            height=width*img.imageHeight/img.imageWidth
            imageflow=Image(str(path),width=width,height=height)
            imageflow.hAlign='CENTER'
            items=[Spacer(1,4),imageflow]
            j=i+1
            while j<len(lines) and not lines[j].strip():j+=1
            if j<len(lines) and lines[j].strip().startswith('*Figure '):
                items.append(para(lines[j].strip().strip('*'),'caption'));i=j+1
            else:i+=1
            story.append(KeepTogether(items));continue
        if line.startswith('|'):
            block=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                block.append(lines[i].strip());i+=1
            story.extend([make_table(block),Spacer(1,7)]);continue
        if line.startswith('*Table '):
            p=para(line.strip('*'),'caption');p.keepWithNext=True
            story.append(p);i+=1;continue
        if line.startswith('- '):
            story.append(para(line[2:],'reference' if in_refs else 'body'));i+=1;continue
        block=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','<!--','![','|','*Table ','- ')):
            block.append(lines[i].strip());i+=1
        story.append(para(' '.join(block)))
    doc=PaperDoc(str(OUT),pagesize=(612,792),leftMargin=72,rightMargin=72,
                 topMargin=65,bottomMargin=60,title='Honor Among Agents',author='Sarosh Thalappil')
    doc.locations={}
    doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
    (BASE/'tmp/pdfs/layout.json').write_text(json.dumps(doc.locations,indent=2))
    print('Wrote',OUT)
    print(json.dumps(doc.locations,indent=2))
    main_pages=doc.locations['References']-1
    print('Main pages:',main_pages)
    if main_pages>8:
        raise SystemExit('Main text exceeds the eight-page submission cap; revise layout.')

if __name__=='__main__':build()
