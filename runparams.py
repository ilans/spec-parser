# the parameters of a run

# SPDX-License-Identifier: Apache-2.0

import argparse
import importlib.util
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


class RunParams(SimpleNamespace):
    def __init__(self, name):
        self._ts = datetime.now(timezone.utc)
        self.log = logging.getLogger(name)
        opt_force = self.process_args()
        self.check_requirements()
        if logging.ERROR in self.log._cache:
            sys.exit(1)
        self.create_output_dirs(opt_force)

    @property
    def autogen_header(self):
        return f"Automatically generated by spec-parser v{self.parser_version} on {self._ts.isoformat()}"

    @property
    def parser_version(self):
        return sys.modules["spec_parser"].__version__

    @property
    def all_as_dict(self):
        return {k: getattr(self, k) for k in ("autogen_header",)}

    def check_requirements(self):
        def check_import_module(module_name, condition):
            if importlib.util.find_spec(module_name) is None:
                self.log.error(f"Python module '{module_name}' is required when {condition} is specified.  Make sure it's installed.")

        def check_external_program(program_name, condition):
            if shutil.which(program_name) is None:
                self.log.error(
                    f"Program '{program_name}' is required when {condition} is specified.  Make sure it's installed and present in your PATH."
                )

        if self.generate_jsondump:
            check_import_module("jsonpickle", "JSON dump generation")
        if self.generate_mkdocs:
            check_import_module("jinja2", "MkDocs generation")
        if self.generate_rdf:
            check_import_module("rdflib", "RDF generation")
        if self.generate_tex:
            check_external_program("pandoc", "TeX generation")
            check_import_module("jinja2", "TeX generation")

    def process_args(self, opts=sys.argv[1:]):
        def check_input_path(p):
            if not p.exists():
                raise argparse.ArgumentTypeError(f"Input directory '{p}' does not exist.")
            if not p.is_dir():
                raise argparse.ArgumentTypeError(f"Input path '{p}' is not a directory.")
            if p.name != "model":
                raise argparse.ArgumentTypeError(f"Input directory '{p}' must be named 'model'.")

        parser = argparse.ArgumentParser(description="Generate documentation from an SPDXv3 model.")

        parser.add_argument("input_dir", type=str, help="Path to the input 'model' directory.")

        parser.add_argument("-d", "--debug", action="store_true", help="Print spec-parser debug information.")
        parser.add_argument("-f", "--force", action="store_true", help="Force overwrite of existing output directories.")
        parser.add_argument("-j", "--generate-jsondump", action="store_true", help="Generate a dump of the model in JSON format.")
        parser.add_argument("-J", "--output-jsondump", type=str, help="Output directory for JSON dump file.")
        parser.add_argument("-m", "--generate-mkdocs", action="store_true", help="Generate MkDocs output.")
        parser.add_argument("-M", "--output-mkdocs", type=str, help="Output directory for MkDocs files.")
        parser.add_argument("-n", "--no-output", action="store_true", help="Perform no output generation, only input validation.")
        parser.add_argument("-o", "--output", type=str, help="Single output directory for all output types.")
        parser.add_argument("-p", "--generate-plantuml", action="store_true", help="Generate PlantUML output.")
        parser.add_argument("-P", "--output-plantuml", type=str, help="Output directory for PlantUML files.")
        parser.add_argument("-r", "--generate-rdf", action="store_true", help="Generate RDF output.")
        parser.add_argument("-R", "--output-rdf", type=str, help="Output directory for RDF files.")
        parser.add_argument("-t", "--generate-tex", action="store_true", help="Generate TeX output.")
        parser.add_argument("-T", "--output-tex", type=str, help="Output directory for TeX files.")
        parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose information.")
        parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {self.parser_version}")
        parser.add_argument("-w", "--generate-webpages", action="store_true", help="Generate web pages output.")
        parser.add_argument("-W", "--output-webpages", type=str, help="Output directory for web pages.")

        opts = parser.parse_args()
        gen_list = ["jsondump", "mkdocs", "plantuml", "rdf", "tex", "webpages"]
        desc_list = ["JSON dump", "MkDocs", "PlantUML", "RDF", "TeX", "Web pages"]

        if opts.verbose:
            self.log.basicConfig(level=logging.INFO)
        if opts.debug:
            self.log.basicConfig(level=logging.DEBUG)

        self.input_path = Path(opts.input_dir)
        check_input_path(self.input_path)

        if opts.no_output:
            self.no_output = True
            if any(getattr(opts, "generate_" + g) for g in gen_list):
                self.log.warning("Incompatible flag combination: -n/--no-output overwrites any generation")
            for g in gen_list:
                setattr(self, "generate_" + g, False)
        else:
            self.no_output = False
            if not any(getattr(opts, "generate_" + g) for g in gen_list):
                for g in gen_list:
                    setattr(self, "generate_" + g, True)
            else:
                for g in gen_list:
                    setattr(self, "generate_" + g, getattr(opts, "generate_" + g))

        if opts.output:
            self.output_path = Path(opts.output)
            if self.output_path.exists() and not opts.force:
                self.log.error("Output directory '{self.output_path}' already exists (use -f/--force to overwrite).")

        for desc, g in zip(desc_list, gen_list):
            genflag = "generate_" + g
            if getattr(self, genflag, False):
                outdir = "output_" + g
                outpath = outdir + "_path"
                if d := getattr(opts, outdir, None):
                    setattr(self, outpath, Path(d))
                elif p := getattr(self, "output_path", None):
                    setattr(self, outpath, p / g)
                else:
                    self.log.error(f"{desc} was specified, but no output directory.")
                if p := getattr(self, outpath, None):
                    if p.exists() and not opts.force:
                        self.log.error(f"Output directory '{p}' already exists (use -f/--force to overwrite).")

        return opts.force


    def create_output_dirs(self, force):
        gen_list = ["jsondump", "mkdocs", "plantuml", "rdf", "tex", "webpages"]
        for g in gen_list:
            genflag = "generate_" + g
            if getattr(self, genflag, False):
                outpath = "output_" + g + "_path"
                p = getattr(self, outpath)
                if force and p.exists():
                    shutil.rmtree(p)
                p.mkdir(parents=True)

