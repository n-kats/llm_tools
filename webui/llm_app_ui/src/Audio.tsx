'use client'

import { Slider } from '@mantine/core'


function AudioControl({volume, setVolume}: {volume: number, setVolume: (v: number) => void}) {

  return (
    <Slider
      label={volume}
      value={volume}
      onChange={setVolume}
      min={0}
      max={1}
      step={0.01}
      thumbSize={14}
    ></Slider>)
}

export default AudioControl
