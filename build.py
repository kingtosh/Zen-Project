from fontTools.designspaceLib import DesignSpaceDocument
from glyphsLib.cli import main
from fontTools.ttLib import newTable, TTFont
import shutil
import subprocess
import multiprocessing
import multiprocessing.pool
from pathlib import Path
import argparse
import ufo2ft, ufoLib2, os, glob
import fontmake.instantiator
import copy

def DSIG_modification(font:TTFont):
    font["DSIG"] = newTable("DSIG")     #need that stub dsig
    font["DSIG"].ulVersion = 1
    font["DSIG"].usFlag = 0
    font["DSIG"].usNumSigs = 0
    font["DSIG"].signatureRecords = []
    font["head"].flags |= 1 << 3        #sets flag to always round PPEM to integer

def step_merge_glyphs_from_ufo(path: Path, instance: ufoLib2.Font, *args) -> None:
    textfile = ""
    for ar in args:
        textfile = ar

    ufo = ufoLib2.Font.open(path)
    if textfile:
        glyphSet = Path(textfile).read_text().split(" ")
        for glyph in glyphSet:
            instance.addGlyph(ufo[glyph])
    else:
        for glyph in ufo:
            if glyph.name not in instance:
                instance.addGlyph(ufo[glyph.name])

def make_static(instance_descriptor, generator):
    if "kaku" in str(instance_descriptor.name).lower():
        instance1 = generator.generate_instance(instance_descriptor)
        instance2 = copy.deepcopy(instance1)

        instance1.info.familyName = "Zen Kaku Gothic N"
        instance2.info.familyName = "Zen Kaku Gothic A"

        instance1.lib['com.github.googlei18n.ufo2ft.filters'] = [{ # extra safe :)
            "name": "flattenComponents",
            "pre": 1,
        }]
        instance2.lib['com.github.googlei18n.ufo2ft.filters'] = [{ # extra safe :)
            "name": "flattenComponents",
            "pre": 1,
        }]
        print ("["+instance_descriptor.name+"] Merging A and N kana")
        step_merge_glyphs_from_ufo(Path("sources/ZenKakuGothic/ZenKakuGothicN-"+instance_descriptor.styleName+".ufo"), instance1)
        step_merge_glyphs_from_ufo(Path("sources/ZenKakuGothic/ZenKakuGothicA-"+instance_descriptor.styleName+".ufo"), instance2)

        print ("["+instance_descriptor.name+"] Generating")

        N_ttf = ufo2ft.compileTTF(
            instance1, 
            removeOverlaps=True, 
            overlapsBackend="pathops", 
            useProductionNames=True,
        )

        A_ttf = ufo2ft.compileTTF(
            instance2, 
            removeOverlaps=True, 
            overlapsBackend="pathops", 
            useProductionNames=True,
        )

        DSIG_modification(A_ttf)
        DSIG_modification(N_ttf)
        print ("["+instance_descriptor.name+"] Saving")

        if instance_descriptor.styleName != "Regular":
            base_load = TTFont()
            TTFont.importXML(base_load, Path("sources/ZenMaruGothic/BASE-"+instance_descriptor.styleName+".ttx"))
            A_ttf["BASE"] = base_load["BASE"]
            N_ttf["BASE"] = base_load["BASE"]

        A_ttf.save("fonts/ttf/"+str(instance_descriptor.familyName).replace(" ","")+"A-"+instance_descriptor.styleName+".ttf")
        N_ttf.save("fonts/ttf/"+str(instance_descriptor.familyName).replace(" ","")+"N-"+instance_descriptor.styleName+".ttf")
    
        autohint("fonts/ttf/"+str(instance_descriptor.familyName).replace(" ","")+"A-"+instance_descriptor.styleName+".ttf")
        autohint("fonts/ttf/"+str(instance_descriptor.familyName).replace(" ","")+"N-"+instance_descriptor.styleName+".ttf")

    else:
        instance = generator.generate_instance(instance_descriptor)

        instance.lib['com.github.googlei18n.ufo2ft.filters'] = [{ # extra safe :)
            "name": "flattenComponents",
            "pre": 1,
        }]

        static_ttf = ufo2ft.compileTTF(
            instance, 
            removeOverlaps=True, 
            overlapsBackend="pathops", 
            useProductionNames=True,
        )

        DSIG_modification(static_ttf)
        print ("["+instance_descriptor.name+"] Saving")
        output = "fonts/ttf/"+str(instance_descriptor.familyName).replace(" ","")+"-"+instance_descriptor.styleName+".ttf"

        if "maru" in str(instance_descriptor.name).lower() and instance_descriptor.styleName != "Regular":
            base_load = TTFont()
            TTFont.importXML(base_load, Path("sources/ZenMaruGothic/BASE-"+instance_descriptor.styleName+".ttx"))
            static_ttf["BASE"] = base_load["BASE"]
        static_ttf.save(output)
        autohint(output)
            


def autohint(file):
    print ("["+str(file)+"] Autohinting")
    subprocess.check_call(
            [
                "ttfautohint",
                "--stem-width",
                "nsn",
                str(file),
                str(file)[:-4]+"-hinted.ttf",
            ]
        )
    shutil.move(str(file)[:-4]+"-hinted.ttf", str(file))

def cleanup():
    # Cleanup
    for ufo in sources.glob("**/*.ufo"):
        shutil.rmtree(ufo)
    os.remove("sources/Kurenaido/Kurenaido.designspace")
    os.remove("sources/ZenAntique/ZenAntique.designspace")
    os.remove("sources/ZenKakuGothic/GothicA_Kana.designspace")
    os.remove("sources/ZenKakuGothic/GothicN_kana.designspace")
    os.remove("sources/ZenKakuGothic/ZenKakuGothic.designspace")
    os.remove("sources/ZenMaruGothic/ZenMaruGothic.designspace")
    os.remove("sources/ZenOldMincho/ZenOldMincho.designspace")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="build MPLUS fonts")
    parser.add_argument("-K", "--kure", action="store_true", dest="kure", help="Export Kurenaido")
    parser.add_argument("-N", "--antique", action="store_true", dest="antique", help="Export Antique")
    parser.add_argument("-G", "--kaku", action="store_true", dest="kaku", help="Export KakuGothic")
    parser.add_argument("-M", "--maru", action="store_true", dest="maru", help="Export MaruGothic")
    parser.add_argument("-O", "--old", action="store_true", dest="old", help="Export OldMincho")

    parser.add_argument("-A", "--all", action="store_true", dest="all", help="All variants")
    parser.add_argument("-S", "--ufo", action="store_true", dest="sources", help="Regen all sources")
    parser.add_argument("-W", "--clean", action="store_false", dest="clean", help="Don't remove all source files")

    args = parser.parse_args()
    sources = Path("sources")

    if args.all:
        args.kure = True
        args.kaku = True
        args.antique = True
        args.maru = True
        args.old = True
        args.sources = True

    if args.sources:
        print ("[ZEN] Generating UFO sources")
        for file in sources.glob("**/*.glyphs"):
            print ("["+str(file)+"] generating source")
            main(("glyphs2ufo", str(file), "--write-public-skip-export-glyphs"))
        
        for ufo in sources.glob("*.ufo"): # need to put this command in all the source UFOs to make sure it is implemented
            source = ufoLib2.Font.open(ufo)
            source.lib['com.github.googlei18n.ufo2ft.filters'] = [{
                "name": "flattenComponents",
                "pre": 1,
            }]
            ufoLib2.Font.save(source)


    if args.kure:
        font = ufoLib2.Font.open("sources/Kurenaido/ZenKurenaido-Regular.ufo")

        font.lib['com.github.googlei18n.ufo2ft.filters'] = [{
            "name": "flattenComponents",
            "pre": 1,
        }]

        exportFont = ufo2ft.compileTTF(
            font, 
            removeOverlaps=True, 
            overlapsBackend="pathops", 
            useProductionNames=True,
        )
        DSIG_modification(exportFont)
        exportFont.save("fonts/ttf/ZenKurenaido-Regular.ttf")
        autohint("fonts/ttf/ZenKurenaido-Regular.ttf")

    if args.antique:
        ds = DesignSpaceDocument.fromfile(sources / "ZenAntique/ZenAntique.designspace")
        ds.loadSourceFonts(ufoLib2.Font.open)
        generator = fontmake.instantiator.Instantiator.from_designspace(ds)

        pool = multiprocessing.pool.Pool(processes=multiprocessing.cpu_count())
        processes = []

        for instance_descriptor in ds.instances: # GOTTA GO FAST
            processes.append(
                pool.apply_async(
                    make_static,
                    (
                        instance_descriptor,
                        generator,
                    ),
                )
            )

        pool.close()
        pool.join()
        for process in processes:
            process.get()
        del processes, pool

    if args.maru:
        ds = DesignSpaceDocument.fromfile(sources / "ZenMaruGothic/ZenMaruGothic.designspace")
        ds.loadSourceFonts(ufoLib2.Font.open)
        generator = fontmake.instantiator.Instantiator.from_designspace(ds)

        pool = multiprocessing.pool.Pool(processes=multiprocessing.cpu_count())
        processes = []

        for instance_descriptor in ds.instances: # GOTTA GO FAST
            processes.append(
                pool.apply_async(
                    make_static,
                    (
                        instance_descriptor,
                        generator,
                    ),
                )
            )

        pool.close()
        pool.join()
        for process in processes:
            process.get()
        del processes, pool

    if args.old:
        ds = DesignSpaceDocument.fromfile(sources / "ZenOldMincho/ZenOldMincho.designspace")
        ds.loadSourceFonts(ufoLib2.Font.open)
        generator = fontmake.instantiator.Instantiator.from_designspace(ds)

        pool = multiprocessing.pool.Pool(processes=multiprocessing.cpu_count())
        processes = []

        for instance_descriptor in ds.instances: # GOTTA GO FAST
            processes.append(
                pool.apply_async(
                    make_static,
                    (
                        instance_descriptor,
                        generator,
                    ),
                )
            )

        pool.close()
        pool.join()
        for process in processes:
            process.get()
        del processes, pool

    if args.kaku:
        ds = DesignSpaceDocument.fromfile(sources / "ZenKakuGothic/ZenKakuGothic.designspace")
        ds.loadSourceFonts(ufoLib2.Font.open)
        generator = fontmake.instantiator.Instantiator.from_designspace(ds)

        pool = multiprocessing.pool.Pool(processes=multiprocessing.cpu_count())
        processes = []

        for instance_descriptor in ds.instances: # GOTTA GO FAST
            processes.append(
                pool.apply_async(
                    make_static,
                    (
                        instance_descriptor,
                        generator,
                    ),
                )
            )

        pool.close()
        pool.join()
        for process in processes:
            process.get()
        del processes, pool

    if args.clean:
        print ("Cleaning build files")
        cleanup()