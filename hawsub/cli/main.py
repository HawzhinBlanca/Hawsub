"""
Hawsub CLI Application.
"""

import click
import sys
import os
import json
from hawsub import __version__
from hawsub.config.loader import load_config
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.benchmark.suite import BenchmarkSuite
from hawsub.providers.factory import get_provider


@click.group()
@click.version_option(version=__version__, message="Hawsub version %(version)s")
def cli():
    """Hawsub — Professional English -> Central Kurdish (Sorani, ckb) Subtitle Localization System."""
    pass


@cli.command()
@click.option("--input", "-i", "input_path", required=True, type=click.Path(exists=True), help="Path to input English SRT/VTT subtitle file.")
@click.option("--project-id", "-p", default="movie_project", help="Unique project identifier.")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), help="Path to custom hawsub.yaml configuration file.")
@click.option("--output-dir", "-o", default="output", help="Output directory for generated subtitle files.")
def process(input_path: str, project_id: str, config_path: str, output_dir: str):
    """Process an English subtitle file through full context-aware Sorani localization pipeline."""
    click.echo(f"Initializing Hawsub pipeline for project: {project_id}")
    cfg = load_config(config_path)
    
    pipeline = DurablePipeline(project_id=project_id, config=cfg)
    results = pipeline.process_file(input_path, output_dir=output_dir)

    click.echo(click.style("✓ Localization complete!", fg="green", bold=True))
    click.echo(f"  SRT Export: {results['srt']}")
    click.echo(f"  ASS Export: {results['ass']}")
    click.echo(f"  VTT Export: {results['vtt']}")
    click.echo(f"  Debug HTML: {results['bilingual_html']}")
    click.echo(f"  QC Report : {results['qc_report']}")


@cli.command()
@click.option("--dataset", "-d", default="tests/gold/gold_dataset.json", type=click.Path(exists=True), help="Gold benchmark dataset path.")
@click.option("--provider", default="mock", help="Provider to evaluate (google | openai | mock).")
@click.option("--model", default="gemini-2.5-pro", help="Model name to evaluate.")
def benchmark(dataset: str, provider: str, model: str):
    """Run cinematic benchmark evaluation on gold dataset pairs."""
    click.echo(f"Running Hawsub benchmark suite on {dataset} using provider={provider}, model={model}...")
    
    p_model = get_provider(provider_name=provider, model_name=model)
    suite = BenchmarkSuite(dataset_path=dataset)
    report = suite.evaluate_model(p_model)

    click.echo("\n" + "=" * 50)
    click.echo(click.style(f"Hawsub Benchmark Results [{report.provider_name} / {report.model_name}]", bold=True))
    click.echo("=" * 50)
    click.echo(f"Total Test Items    : {report.total_items}")
    click.echo(f"Passed Items        : {report.passed_items}")
    click.echo(f"Literal Error Count : {report.literal_error_count}")
    click.echo(click.style(f"Overall Score       : {report.overall_benchmark_score * 100:.1f}%", fg="cyan", bold=True))
    click.echo("=" * 50)


@cli.command()
@click.option("--text", "-t", required=True, help="Input Kurdish text to normalize.")
def normalize(text: str):
    """Normalize Sorani Kurdish text to canonical orthography."""
    norm = SoraniNormalizer()
    res = norm.normalize(text)
    click.echo(f"Input     : {text}")
    click.echo(f"Normalized: {res}")


if __name__ == "__main__":
    cli()
