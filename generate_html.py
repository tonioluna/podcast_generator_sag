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

_header_items = dict ( temporada              =  "Temporada"               ,
                       programa_num_global    =  "Num Programa Global"     ,
                       programa_num_temporada =  "Num Programa Temporada"  ,
                       fecha                  =  "Fecha"                   ,
                       tema                   =  "Tema"                    ,
                       tema_descripcion       =  "Tema Descripcion"        ,
                       recomendacion_tipo     =  "Recomendacion Tipo"      ,
                       recomendacion_titulo   =  "Recomendacion Titulo"    ,
                       recomendacion_mas_info =  "Recomendacion Mas Info"  ,
                       recomendacion_link     =  "Recomendacion Link"      ,
                       musica_titulo          =  "Musica Titulo"           ,
                       musica_compositor      =  "Musica Compositor"       ,
                       musica_interprete      =  "Musica Interprete"       ,
                       musica_origen          =  "Musica Origen"           ,
                       musica_mas_info        =  "Musica Mas Info"         ,
                       musica_link            =  "Musica Link"             ,
                       archivo_audio          =  "Archivo Audio"           ,
                       advertencia            =  "Advertencia"             ,
                       fe_de_erratas          =  "Fe de Erratas"           ,
                    )

# Items which should be non-None
_required_header_items = ("temporada",
                          "programa_num_global",
                          "fecha",
                          "tema",
                          "archivo_audio",
                          )

_style_season = "font-size:18pt;font-weight:bold;color:#22B;"
_style_header = "font-size:15pt;font-weight:bold;"
_style_body = "font-family:Lucida Grande,Lucida Sans Unicode,Verdana,sans-serif; font-size:11pt; line-height: 180%;"
_style_date = "font-size:11pt;color:#22B;"
_style_warning = "font-size:11pt;font-weight:bold;color:#D60;"
_style_errata = "color:#909;font-weight:bold;"
#_style_item_type = "text-decoration: underline;"
_style_item_type = _style_date
_style_item_title = "font-weight:bold;"
_style_download_link = _style_date

_audio_url_base = "http://www.sagdl.org/sites/default/files/unaventanaaluniverso/"

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

        data = types.SimpleNamespace()
        data.seasons = []
        data.programs = {}

        stop_read = False
        # Read the data
        row_num = 1
        for row in reader:
            row = list(row)
            row_num += 1
            row_text = ("".join(row)).replace(" ","")
            if row_text == "": continue
            if "#SKIPROW" in row_text:
                _log.warning("Skipping row %i"%(row_num,))
                continue
            
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
            
            if d.temporada not in data.seasons:
                data.seasons.append(d.temporada)
                
            assert d.programa_num_global not in data.programs, "Duplicated program with number %s at row %i"%(d.programa_num_global, row_num)
            data.programs[d.programa_num_global] = d

        _log.info("Read %i podcast entries"%(len(data.programs)))
        return data


def write_html(data, filename = None):
    if filename == None:
        filename = _default_html

    _log.info("Writting results to %s"%(filename, ))
    kwargs={}
    kwargs['encoding']='utf-8'
    with open(filename, "w", **kwargs) as fh:
        # Body style
        fh.write('<span style="%s">\n'%(_style_body))
        fh.write('<p>En esta página podrás encontrar grabaciones de ediciones anteriores de <a href="/actividades/radio">Una Ventana al Universo</a>&nbsp;transmitidas en Jalisco Radio.</p>')
        
        seasons = []
        seasons.extend(data.seasons)
        seasons.sort(reverse=True)
        
        programs = list(data.programs.keys())
        programs.sort(reverse = True)
        
        
        fh.write('<p><h1 id="indice"><span style="%s">Índice</span></h1>\n'%(_style_season,))
        fh.write('<ul>\n')
            
        for season in seasons:
            fh.write('<li><span style="%s">Temporada %s</span>\n'%(_style_item_title, season))
            fh.write('<ul>\n')
            for num in programs:
                entry = data.programs[num]
                if entry.temporada != season: 
                    continue
                fh.write('<li><a href="#programa_%s">Programa %s, %s</a></li>\n'%(entry.programa_num_global, entry.programa_num_global, entry.fecha))
            fh.write('</ul>\n')
        fh.write('</ul>\n')
        fh.write('</p>\n')
            
        for season in seasons:
        
            fh.write('<h1><span style="%s">Temporada %s</span></h1>\n'%(_style_season, season,))
            
            for num in programs:
                entry = data.programs[num]
                if entry.temporada != season: 
                    continue
                
                fh.write('<p>\n')
                
                # Program number
                fh.write('<hr id="programa_%s"/>\n'%(entry.programa_num_global,))
                fh.write('<span style="%s">Programa %s</span><br/>\n'%(_style_header, entry.programa_num_global,))
                
                # Season and date
                if entry.programa_num_temporada is not None:
                    fh.write('<span style="%s">Programa #%s de la Temporada #%s, emitido el %s</span><br/>\n'
                             ''%(_style_date, entry.programa_num_temporada, entry.temporada, entry.fecha,))
                else:
                    fh.write('<span style="%s">Programa de la Temporada #%s, emitido el %s</span><br/>\n'
                             ''%(_style_date, entry.temporada, entry.fecha,))
                
                # Topic and description
                fh.write('<span style="%s">Tema</span>: <span style="%s">%s</span>\n'
                    ''%(_style_item_type, _style_item_title, entry.tema))
                if entry.tema_descripcion is not None:
                    fh.write(', %s.'%(entry.tema_descripcion))
                fh.write('<br/>\n')
                
                # Suggested item
                if entry.recomendacion_titulo is not None:
                    fh.write('<span style="%s">Recomendación</span>: <span style="%s">\n'
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
                    fh.write('<br/>\n')
                    
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
                    if entry.musica_compositor is not None:
                        fh.write(', compuesta por %s'%(entry.musica_compositor))
                    if entry.musica_interprete is not None:
                        fh.write(', interpretada por %s'%(entry.musica_interprete))
                    if entry.musica_origen is not None:
                        fh.write(', obtenida de %s'%(entry.musica_origen))
                    if entry.musica_mas_info is not None:
                        fh.write('. %s'%(entry.musica_mas_info))
                    fh.write('.<br/>\n')

                if entry.fe_de_erratas is not None:
                    fh.write('<span style="%s">Fe de Erratas: </span><span style="%s">%s</span><br/>\n'
                             ''%(_style_item_type, _style_errata, entry.fe_de_erratas,))
                
                if entry.advertencia is not None:
                    fh.write('<span style="%s">&#128681; %s &#128681;</span><br/>\n'
                             ''%(_style_warning, entry.advertencia,))
                
                # Audio!
                audio_url = _audio_url_base + entry.archivo_audio
                if not url_exists(audio_url):
                    raise Exception("Audio file does not exist for program %s: %s"
                        ""%(entry.programa_num_global, audio_url))
                
                fh.write('<audio controls="" style="width: -webkit-fill-available;"><source src="%s" type="audio/mpeg" /></audio>\n'
                    ''%(audio_url,))

                fh.write('<span style="%s"><a href="%s" download="podcast.una_ventana_al_universo.programa_%s.mp3">'
                    'Descarga el podcast en formato mp3</a><br/><a href="#indice">Regresar al Índice</a></span>\n'
                    ''%(_style_download_link, audio_url, entry.programa_num_global))
                
                fh.write('</p><br/>\n')
                
            

        fh.write('<br/><br/>Página actualizara por última vez el %s usando un <a href="https://github.com/tonioluna/podcast_generator_sag" target="_BLANK">método terrible</a>.<br /><br />\n\n'%(time.strftime("%d/%m/%Y %H:%M:%S")))

        # Overall span for font style
        fh.write('</span>\n')
        

        fh.write("</span>\n")

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