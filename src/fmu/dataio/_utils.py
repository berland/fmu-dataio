"""Module for private utilities/helpers for DataIO class."""
import hashlib
import json
import logging
import uuid
from collections import OrderedDict
from os.path import join
from pathlib import Path

from . import _oyaml as oyaml

logger = logging.getLogger(__name__)


def construct_filename(
    name,
    pretagname=None,
    tagname=None,
    t1=None,
    t2=None,
    subfolder=None,
    fmu=1,
    outroot="../../share/results/",
    loc="surface",
    verbosity="WARNING",
):
    """Construct filename stem according to datatype (class) and fmu style.

    fmu style 1:

        surface:
            namehorizon--tagname
            namehorizon--tagname--t1
            namehorizon--tagname--t2_t1

            e.g.
            topvolantis--ds_gf_extracted
            therys--facies_fraction_lowershoreface

        grid (geometry):
            gridname--<hash>

        gridproperty
            gridname--proptagname
            gridname--tagname--t1
            gridname--tagname--t2_t1

            e.g.
            geogrid_valysar--phit

    Destinations accoring to datatype.

    Removing dots from filename:
    Currently, when multiple dots in a filename stem,
    XTgeo, using pathlib, will interpret the part after the
    last dot as the file suffix, and remove it. This causes
    errors in the output filenames. While this is being
    taken care of in XTgeo, we temporarily sanitize dots from
    the outgoing filename only to avoid this.

    Space will also be replaced in file names.

    Returns stem for file name and destination
    """
    logger.setLevel(level=verbosity)

    stem = "unset"

    outroot = Path(outroot)

    if fmu == 1:

        stem = name.lower()

        if tagname:
            stem += "--" + tagname.lower()

        if pretagname:
            stem = pretagname.lower() + "--" + stem

        if t1 and not t2:
            stem += "--" + str(t1).lower()

        elif t1 and t2:
            stem += "--" + str(t2).lower() + "_" + str(t1).lower()

        stem = stem.replace(".", "_").replace(" ", "_")

        if loc == "surface":
            dest = outroot / "maps"
        elif loc == "grid":
            dest = outroot / "grids"
        elif loc == "table":
            dest = outroot / "tables"
        elif loc == "polygons":
            dest = outroot / "polygons"
        elif loc == "cube":
            dest = outroot / "cubes"
        else:
            dest = outroot / "other"

        if subfolder:
            dest = dest / subfolder

    return stem, dest


def verify_path(dataio, filedest, filename, ext, dryrun=False):
    logger.setLevel(level=dataio._verbosity)

    logger.debug("Incoming filedest is %s", filedest)
    logger.debug("Incoming filename is %s", filename)
    logger.debug("Incoming ext is %s", ext)

    folder = dataio._pwd / filedest  # filedest shall be relative path to PWD

    path = Path(folder) / filename.lower()
    path = path.with_suffix(path.suffix + ext)
    abspath = path.resolve()

    logger.debug("path is %s", path)

    if not dryrun:
        if path.parent.exists():
            logger.info("Folder exists")
        else:
            if dataio.createfolder:
                logger.info("No such folder, will create")
                path.parent.mkdir(parents=True, exist_ok=True)
            else:
                raise IOError(f"Folder {str(path.parent)} is not present.")

    # create metafile path
    metapath = (
        (Path(folder) / ("." + filename.lower())).with_suffix(ext + ".yml")
    ).resolve()

    # relative path
    relpath = str(filedest).replace("../", "")
    if dataio._realfolder is not None and dataio._iterfolder is not None:
        relpath = join(f"{dataio._realfolder}/{dataio._iterfolder}", relpath)
    relpath = join(f"{relpath}/{filename.lower()}{ext}")

    logger.info("Full path to the actual file is: %s", abspath)
    logger.info("Full path to the metadata file (if used) is: %s", metapath)
    logger.info("Relative path to actual file: %s", relpath)

    return path, metapath, relpath, abspath


def drop_nones(dinput: dict) -> dict:
    """Recursively drop Nones in dict dinput and return a new dict."""
    # https://stackoverflow.com/a/65379092
    dd = {}
    for key, val in dinput.items():
        if isinstance(val, dict):
            dd[key] = drop_nones(val)
        elif isinstance(val, (list, set, tuple)):
            # note: Nones in lists are not dropped
            # simply add "if vv is not None" at the end if required
            dd[key] = type(val)(
                drop_nones(vv) if isinstance(vv, dict) else vv for vv in val
            )
        elif val is not None:
            dd[key] = val
    return dd


def export_metadata_file(yfile, metadata, savefmt="yaml", verbosity="WARNING") -> None:
    """Export genericly and ordered to the complementary metadata file."""
    logger.setLevel(level=verbosity)
    if metadata:

        xdata = drop_nones(metadata)

        if savefmt == "yaml":
            yamlblock = oyaml.safe_dump(xdata)
            with open(yfile, "w") as stream:
                stream.write(yamlblock)
        else:
            jfile = str(yfile).replace(".yml", ".json")
            jsonblock = json.dumps(xdata, default=str, indent=2)
            with open(jfile, "w") as stream:
                stream.write(jsonblock)

    else:
        raise RuntimeError(
            "Export of metadata was requested, but no metadata are present."
        )
    logger.info("Yaml file on: %s", yfile)


def md5sum(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as fil:
        for chunk in iter(lambda: fil.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def size(fname):
    return Path(fname).stat().st_size


def uuid_from_string(string):
    """Produce valid and repeteable UUID4 as a hash of given string"""
    return uuid.UUID(hashlib.md5(string.encode("utf-8")).hexdigest())


def read_parameters_txt(pfile):
    """Read the parameters.txt file and convert to a dict.

    The parameters.txt file has this structure::

      SENSNAME rms_seed
      SENSCASE p10_p90
      RMS_SEED 1000
      KVKH_CHANNEL 0.6
      KVKH_CREVASSE 0.3
      GLOBVAR:VOLON_FLOODPLAIN_VOLFRAC 0.256355
      GLOBVAR:VOLON_PERMH_CHANNEL 1100
      GLOBVAR:VOLON_PORO_CHANNEL 0.2
      LOG10_GLOBVAR:FAULT_SEAL_SCALING 0.685516
      LOG10_MULTREGT:MULT_THERYS_VOLON -3.21365
      LOG10_MULTREGT:MULT_VALYSAR_THERYS -3.2582

    ...but may also appear on a justified format, with leading
    whitespace and tab-justified columns, legacy from earlier
    versions but kept alive by some users::

                            SENSNAME     rms_seed
                            SENSCASE     p10_p90
                            RMS_SEED     1000
                        KVKH_CHANNEL     0.6
          GLOBVAR:VOLON_PERMH_CHANNEL    1100
      LOG10_GLOBVAR:FAULT_SEAL_SCALING   0.685516
      LOG10_MULTREGT:MULT_THERYS_VOLON   -3.21365

    This should be parsed as::

        {
        "SENSNAME": "rms_seed"
        "SENSCASE": "p10_p90"
        "RMS_SEED": 1000
        "KVKH_CHANNEL": 0.6
        "KVKH_CREVASSE": 0.3
        "GLOBVAR": {"VOLON_FLOODPLAIN_VOLFRAC": 0.256355, ...etc}
        }
    """

    logger.debug("Reading parameters.txt from %s", pfile)

    with open(pfile, "r") as stream:
        buffer = stream.read().splitlines()

    logger.debug("buffer is of type %s", type(buffer))
    logger.debug("buffer has %s lines", str(len(buffer)))

    buffer = [":".join(line.split()) for line in buffer]

    param = OrderedDict()
    for line in buffer:
        items = line.split(":")
        if len(items) == 2:
            param[items[0]] = check_if_number(items[1])
        elif len(items) == 3:
            if items[0] not in param:
                param[items[0]] = OrderedDict()

            param[items[0]][items[1]] = check_if_number(items[2])
        else:
            raise RuntimeError(
                f"Unexpected structure of parameters.txt, line is: {line}"
            )

    return param


def check_if_number(value):
    """Check if value (str) looks like a number and return the converted value."""

    res = None
    try:
        res = int(value)
    except ValueError:
        try:
            res = float(value)
        except ValueError:
            pass

    if res is not None:
        return res

    return value
