offswitch
=========

Destroy compute nodes.

## Usage

    $ python -m offswitch -h
    usage: __main__.py [-h] [-s STRATEGY]
    
    Destroy compute nodes
    
    optional arguments:
      -h, --help            show this help message and exit
      -s STRATEGY, --strategy STRATEGY
                            strategy file [strategy.sample.json]

## Roadmap

  - Glob removals, e.g.: `python -m offswitch -g /unclustered/any-cluster*`
  - Provider removals, e.g.: `python -m offswitch -p SOFTLAYER`
  - Improved success output and handling of provider errors
