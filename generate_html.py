# -*- coding: utf-8 -*-
# Antonio Luna, Aug 2019
# License: WTFPL

import os
import time
import sys
import logging
import csv
import traceback
import types
import pprint
import requests
from xml.sax.saxutils import escape

_default_html = "podcast.html"

_header_items = dict ( temporada              =  "Temporada"             ,
                       programa_num_global    =  "Num Programa Global"   ,
                       programa_num_temporada =  "Num Programa Temporada"   ,
                       fecha                  =  "Fecha"                 ,
                       tema                   =  "Tema"                  ,
                       tema_descripcion       =  "Tema Descripcion",
                       recomendacion_tipo     =  "Recomendacion Tipo"    ,
                       recomendacion_titulo   =  "Recomendacion Titulo"  ,
                       recomendacion_mas_info =  "Recomendacion Mas Info"  ,
                       recomendacion_link     =  "Recomendacion Link"    ,
                       musica_titulo          =  "Musica Titulo"         ,
                       musica_autor           =  "Musica Autor"         ,
                       musica_mas_info        =  "Musica Mas Info"      ,
                       musica_link            =  "Musica Link"          ,
                       archivo_audio          =  "Archivo Audio" ,
                    )

# Items which should be non-None
_required_header_items = ("temporada",
                          "programa_num_global",
                          "programa_num_temporada",
                          "fecha",
                          "tema",
                          "archivo_audio",
                          )

_style_header = "font-size:16pt;font-weight:bold;"
_style_body = "font-family:Lucida Grande,Lucida Sans Unicode,Verdana,sans-serif; font-size:11pt; line-height: 180%;"
_style_date = "font-size:10pt;color:#22B;"
#_style_item_type = "text-decoration: underline;"
_style_item_type = _style_date
_style_item_title = "font-weight:bold;"
_style_download_link = _style_date

_audio_url_base = "http://www.sagdl.org/sites/default/files/"

###############################################
### Custom Colors
###############################################

## Event types
#_event_type_color_codes = {_event_type_weekly_session    : 0x8dd29f,
#                           _event_type_lunaria_workshop  : 0xe6b37e,
#                           _event_type_lunaria_talk      : 0xefdac4,
#                           _event_type_radio_jalisco     : 0xf7dae7,
#                           _event_type_radio_maria       : 0xd1a1b7,
#                           _event_type_camping           : 0x6fa8dc,
#                           _event_type_expedition        : 0x4fd1cb,
#                           _event_type_NdE               : 0xd7e9fa,
#                           }
#

def startLog():
    filename = os.path.splitext(os.path.basename(__file__))[0] + ".log"
    with open(filename, "w") as fh:
        fh.write("Starting on %s\n"%(time.ctime()))
    _log = logging.getLogger(sys.argv[0])
    _log.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    fh = logging.FileHandler(filename = filename)
    fh.setLevel(logging.DEBUG)


    # create formatter
    formatter = logging.Formatter('%(levelname)s - %(message)s')

    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    _log.addHandler(ch)
    _log.addHandler(fh)

    _log.info("Started on %s at %s running under %s"%(time.ctime(),
                                                     os.environ.get("COMPUTERNAME", "UNKNOWN_COMPUTER"),
                                                     os.environ.get("USERNAME", "UNKNOWN_USER"),))

    return _log

def url_exists(path):
    r = requests.head(path)
    exists = r.status_code == requests.codes.ok
    _log.info("URL %s: %s"%("exists" if exists else "DOES NOT EXIST", path))
    return exists

def read_csv(input):
    _log.info("Reading data from %s"%(input, ))
    kwargs={}
    kwargs['encoding']='utf-8'
    with open(input, "r", **kwargs) as fh:
        #reader = csv.reader(fh)
        reader = csv.reader(fh, dialect=csv.excel)
        header_row = next(reader)

        header = {}
        #read the header
        for index, cell in enumerate(header_row):
            #cell = cell.lower()
            _log.debug("Checking header cell %s"%(repr(cell)))
            match_found = False
            for hdr_key, hdr_txt in _header_items.items():
                if hdr_txt == cell:
                    if hdr_key in header:
                        _log.warning("Duplicated header item %s (as %s) at col %i (it was col %i before)"
                            ""%(repr(hdr_key), repr(hdr_txt), index, header[hdr_key]))
                    header[hdr_key] = index
                    _log.debug("%s matches for %s"%(repr(cell), hdr_key))
                    match_found = True
                    break
            if not match_found:
                _log.warning("Un-matched header item at col %i: %s"%(index, repr(cell)))
        # check we got the full header
        if len(header) != len(_header_items):
            _log.error("Not all items were found on the header")
            #exp = ["%s (as %s)"%(hdr_key, hdr_txt) for hdr_key, hdr_txt in _header_items.items() ]
            exp = ["%s"%(hdr_txt) for hdr_txt in _header_items.values() ]
            exp.sort()
            found = [_header_items[k] for k in header.keys()]
            found.sort()
            _log.info("   Found items: %s"%(", ".join([repr(v) for v in found])))
            _log.info("Expected items: %s"%(", ".join([repr(v) for v in exp])))
            _log.info("Missing items: %s"%(", ".join([repr(v) for v in list(set(exp) - set(found))])))
            raise Exception("Header missing items")
        _log.info("All header items were found")

        max_req_col = max(header.values())

        data = []

        stop_read = False
        # Read the data
        row_num = 0
        for row in reader:
            row = list(row)
            row_num += 1
            row_text = ("".join(row)).replace(" ","")
            if row_text == "": continue
            
            # Pad required columns. If some cells are empty not all columns will be added
            while len(row) <= max_req_col:
                row.append("")

            d = types.SimpleNamespace()
            for hdr_key in _header_items.keys():
                v = row[header[hdr_key]]
                v = v.strip().strip(".").strip(",")
                if v == "":
                    assert hdr_key not in _required_header_items, \
                        "item %s from row %s is not defined and it must be"\
                        ""%(repr(_header_items[hdr_key]), row_num)
                    v = None
                setattr(d, hdr_key, v)
            data.append(d)

        _log.info("Read %i podcast entries"%(len(data)))
        return data


def write_html(data, filename = None):
    if filename == None:
        filename = _default_html

    _log.info("Writting results to %s"%(filename, ))
    _log.debug(pprint.pformat(data))
    kwargs={}
    kwargs['encoding']='utf-8'
    with open(filename, "w", **kwargs) as fh:
        fh.write('</span style="font-family:Georgia,"Times New Roman",Times,serif;">')
        fh.write('<p>En esta página podrás encontrar los programas de radio de <a href="/actividades/radio">Una Ventana al Universo</a>&nbsp;transmitidos en Jalisco Radio.</p>')
        fh.write("Ultima actualizaci&oacute;n: %s<br /><br />\n"%(time.strftime("%d/%m/%Y %H:%M:%S")))

        for entry in data:
            fh.write('<p>')
            
            # Program number
            fh.write('<hr>')
            fh.write('<span style="%s">Programa %s</span><br/>'%(_style_header, entry.programa_num_global,))
            
            # Body style
            fh.write('<span style="%s">'%(_style_body))
            
            # Season and date
            fh.write('<span style="%s">Programa #%s de la Temporada #%s, emitido el %s</span><br/>'
                     ''%(_style_date, entry.programa_num_temporada, entry.temporada, entry.fecha,))
            
            # Topic and description
            fh.write('<span style="%s">Tema</span>: <span style="%s">%s</span>'
                ''%(_style_item_type, _style_item_title, entry.tema))
            if entry.tema_descripcion is not None:
                fh.write(', %s.'%(entry.tema_descripcion))
            fh.write('<br/>')
            
            # Suggested item
            if entry.recomendacion_titulo is not None:
                fh.write('<span style="%s">Recomendación</span>: <span style="%s">'
                    ''%(_style_item_type, _style_item_title))
                if entry.recomendacion_link is not None:
                    fh.write('<a href="%s" target="_BLANK">'%(entry.recomendacion_link))
                fh.write('%s'%(entry.recomendacion_titulo))
                if entry.recomendacion_link is not None:
                    fh.write('</a>')
                fh.write('</span>')
                if entry.recomendacion_tipo is not None:
                    fh.write(' (%s)'%(entry.recomendacion_tipo))
                if entry.recomendacion_mas_info is not None:
                    fh.write('. %s.'%(entry.recomendacion_mas_info))
                fh.write('<br/>')
                
            # Music
            if entry.musica_titulo is not None:
                fh.write('<span style="%s">Música</span>: <span style="%s">'
                    ''%(_style_item_type, _style_item_title))
                if entry.musica_link is not None:
                    fh.write('<a href="%s" target="_BLANK">'%(entry.musica_link))
                fh.write('%s'%(entry.musica_titulo))
                if entry.musica_link is not None:
                    fh.write('</a>')
                fh.write('</span>')
                if entry.musica_autor is not None:
                    fh.write(', compuesta por %s'%(entry.musica_autor))
                if entry.musica_mas_info is not None:
                    fh.write(', %s'%(entry.musica_mas_info))
                fh.write('<br/>')

            # Audio!
            audio_url = _audio_url_base + entry.archivo_audio
            if not url_exists(audio_url):
                raise Exception("Audio file does not exist for program %s: %s"
                    ""%(entry.programa_num_global, audio_url))
            
            fh.write('<audio controls="" style="width: -webkit-fill-available;"><source src="%s" type="audio/mpeg" /></audio>'
                ''%(audio_url,))

            fh.write('<span style="%s"><a href="%s" download="podcast_sag_programa_%s.mp3">'
                'Descarga el podcast en formato mp3</a></span>'
                ''%(_style_download_link, audio_url, entry.programa_num_global))
            
            
            # Overall span for font style
            fh.write('</span>')
            fh.write('</p>')
            
            


        fh.write("</span>")

def escape_html(txt):
    if not py3:
        txt = txt.encode("utf-8", "ignore")
    return escape(txt)

def main():
    global _log

    _log = startLog()

    try:
        input = get_input()

        data = read_csv(input)

        write_html(data)

    except Exception as ex:
        _log.error("Caught top level exception: %s"%(ex, ))
        _log.info(traceback.format_exc())
        return 1
    return 0

def get_input():
    # Get the inpout file
    if len(sys.argv) > 1:
        if not os.path.isfile(sys.argv[1]):
            raise Exception("Not a valid input file: %s"%(sys.argv[1]))

        return sys.argv[1]
    _log.warning("No input file was provided. Using default.")
    return os.path.join(os.path.dirname(__file__), "podcasts.csv")


if __name__ == "__main__":
    exit(main())