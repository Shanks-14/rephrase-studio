"""Run from the backend folder with (venv) active:  python diag.py
Prints why WordNet / rhyme support is or isn't working."""
import sys, traceback

print("python  :", sys.executable)
print("version :", sys.version.split()[0])

try:
    import nltk
    print("nltk    : OK", nltk.__version__)
except Exception:
    print("nltk    : NOT INSTALLED in this python")
    traceback.print_exc()
    nltk = None

try:
    import pronouncing
    print("pronounc: OK")
    print("  rhymes(love) ->", pronouncing.rhymes("love")[:4])
except Exception:
    print("pronounc: FAILED")
    traceback.print_exc()

if nltk:
    print("nltk data search paths:", nltk.data.path)
    from nltk.corpus import wordnet as wn
    try:
        print("wordnet : OK ->", wn.synsets("happy")[0])
    except LookupError:
        print("wordnet : corpus MISSING, trying to download...")
        for pkg in ("wordnet", "omw-1.4"):
            try:
                print("  download", pkg, "->", nltk.download(pkg))
            except Exception:
                print("  download", pkg, "RAISED:")
                traceback.print_exc()
        try:
            print("wordnet after download ->", wn.synsets("happy")[0])
        except Exception:
            print("wordnet still FAILING:")
            traceback.print_exc()
    except Exception:
        print("wordnet : FAILED")
        traceback.print_exc()