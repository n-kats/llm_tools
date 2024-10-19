'use client'

import { useState, useEffect, useRef } from 'react'
import { MantineProvider, Button, Paper, Grid, Text, Image, Container, Loader } from '@mantine/core'
import theme from './Theme.tsx'
import Client from './Client.tsx'
import UrlInput from './UrlInput.tsx'
import Markdown from './Markdown.tsx'
import AudioControl from './Audio.tsx'

export default function DocumentViewer() {
  const [url, setUrl] = useState('')
  const [requestId, setRequestId] = useState('')
  const [pageNum, setPageNum] = useState(1)
  const [maxPageNum, setMaxPageNum] = useState(1)
  const [explanation, setExplanation] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [isInitialized, setIsInitialized] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [volume, setVolume] = useState(0.5)
  const containerRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const client = new Client()

  const fetchExplanationAndImage = async (reqId: string, page: number) => {
    var error: boolean = false
    setIsLoading(true)
    const runExplain = client.explain(reqId, page).then((explanation: string | null) => {
      if (explanation !== null) {
        setExplanation(explanation)
      } else {
        error = true
      }
    })
    const runImage = client.image(reqId, page).then((imageUrl: string | null) => {
      if (imageUrl !== null) {
        setImageUrl(imageUrl)
      } else {
        error = true
      }
    })
    await Promise.all([runExplain, runImage])
    await client.audio(reqId, page).then((audioUrl: string | null) => {
      if (audioUrl !== null) {
        setAudioUrl(audioUrl)
      } else {
        error = true
      }
    })

    setIsLoading(false)
    if (error) {
      console.error('Error fetching explanation and image')
    }
  }

  const regenerate = async (reqId: string, page: number) => {
    var error: boolean = false
    setIsLoading(true)
    const runExplain = client.regenerate(reqId, page).then((explanation: string | null) => {
      if (explanation !== null) {
        setExplanation(explanation)
      } else {
        error = true
      }
    })
    const runImage = client.image(reqId, page).then((imageUrl: string | null) => {
      if (imageUrl !== null) {
        setImageUrl(imageUrl)
      } else {
        error = true
      }
    })
    await Promise.all([runExplain, runImage])
    await client.audio(reqId, page).then((audioUrl: string | null) => {
      if (audioUrl !== null) {
        setAudioUrl(audioUrl)
      } else {
        error = true
      }
    })

    setIsLoading(false)
    if (error) {
      console.error('Error fetching explanation and image')
    }
  }


  const changePage = (newPage: number) => {
    const validPage = Math.max(1, Math.min(newPage, maxPageNum))
    if (validPage !== pageNum) {
      setPageNum(validPage)
      fetchExplanationAndImage(requestId, validPage)
    }
  }

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'PageUp' || event.key === 'ArrowUp') {
        changePage(pageNum - 1)
      } else if (event.key === 'PageDown' || event.key === 'ArrowDown') {
        changePage(pageNum + 1)
      }
    }

    if (isInitialized) {
      window.addEventListener('keydown', handleKeyDown)
    }

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [pageNum, maxPageNum, requestId, isInitialized])

  return (
    <MantineProvider theme={theme}>
      <Container ref={containerRef}>
        <Grid>
          <Grid.Col span={6}>
            <UrlInput onGetResult={({ request_id, page_num, url }) => {
              setRequestId(request_id)
              setMaxPageNum(page_num)
              setPageNum(1)
              setUrl(url)
              setIsInitialized(true)
              fetchExplanationAndImage(request_id, 1)
            }} />
          </Grid.Col>
          <Grid.Col span={6}>
            <Button onClick={() => regenerate(requestId, pageNum)}>Regenerate</Button>
            <AudioControl volume={volume} setVolume={(value) => {
              console.log('setting volume')
              console.log(value)
              setVolume(value)
              if (audioRef.current) {
                audioRef.current.volume = value
              }
            }} />
          </Grid.Col>
        </Grid>
        <Grid type="container">
          <Grid.Col span={6}>
            <Paper>
              {isInitialized && (
                <>
                  <Text>URL: {url} </Text>
                  <Text>Page: {pageNum} / {maxPageNum} </Text>
                  {!isLoading && (<audio ref={audioRef} src={audioUrl} autoPlay></audio>)}
                  {isLoading ? <Loader /> : <Markdown> {explanation} </Markdown>}
                </>
              )}
            </Paper>
          </Grid.Col>
          <Grid.Col span={6}>
            {isInitialized && imageUrl && (
              <Image src={imageUrl} alt={`Page ${pageNum}`} fit="contain" />
            )}
          </Grid.Col>
        </Grid>
      </Container>
    </MantineProvider>
  )
}
