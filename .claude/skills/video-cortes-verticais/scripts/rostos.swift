// rostos.swift — detecção de rosto com o framework Vision (VNDetectFaceRectanglesRequest).
// Amostra alguns quadros por segundo de um vídeo e grava um JSON com as caixas NORMALIZADAS (0–1, origem no canto
// superior esquerdo). Não desenha nada e não usa rede. Compilado uma vez por enquadrar.py (swiftc, sob a trava do kit).
//
// uso: rostos <video> <saida.json> [--fps 3] [--inicio S] [--fim S] [--lado 640]

import AVFoundation
import CoreGraphics
import Foundation
import Vision

func opcao(_ nome: String, _ padrao: Double) -> Double {
    let a = CommandLine.arguments
    if let i = a.firstIndex(of: nome), i + 1 < a.count, let v = Double(a[i + 1]) { return v }
    return padrao
}

func sair(_ codigo: Int32, _ mensagem: String) -> Never {
    FileHandle.standardError.write((mensagem + "\n").data(using: .utf8)!)
    exit(codigo)
}

let argumentos = CommandLine.arguments
if argumentos.count < 3 { sair(64, "uso: rostos <video> <saida.json> [--fps 3] [--inicio S] [--fim S] [--lado 640]") }
let entrada = URL(fileURLWithPath: argumentos[1])
let saida = URL(fileURLWithPath: argumentos[2])
if !FileManager.default.fileExists(atPath: entrada.path) { sair(1, "rostos: vídeo não encontrado: \(entrada.path)") }

let asset = AVURLAsset(url: entrada)
guard let trilha = asset.tracks(withMediaType: .video).first else { sair(1, "rostos: o arquivo não tem trilha de vídeo") }
let duracao = CMTimeGetSeconds(asset.duration)
let tamanho = trilha.naturalSize.applying(trilha.preferredTransform)
let largura = abs(tamanho.width), altura = abs(tamanho.height)

let fps = max(0.5, min(15, opcao("--fps", 3)))
let inicio = max(0, opcao("--inicio", 0))
let fim = min(duracao, opcao("--fim", duracao))
let lado = max(160, opcao("--lado", 640))
if fim <= inicio { sair(64, "rostos: trecho vazio (--inicio \(inicio) --fim \(fim); o vídeo tem \(duracao) s)") }

let gerador = AVAssetImageGenerator(asset: asset)
gerador.appliesPreferredTrackTransform = true
gerador.maximumSize = CGSize(width: lado, height: lado)
gerador.requestedTimeToleranceBefore = CMTime(value: 1, timescale: 20)
gerador.requestedTimeToleranceAfter = CMTime(value: 1, timescale: 20)

var quadros: [[String: Any]] = []
var falhas = 0
var n = 0
while true {
    let t = inicio + Double(n) / fps
    if t >= fim { break }
    n += 1
    autoreleasepool {
        var rostos: [[String: Double]] = []
        if let imagem = try? gerador.copyCGImage(at: CMTime(seconds: t, preferredTimescale: 600), actualTime: nil) {
            let pedido = VNDetectFaceRectanglesRequest()
            do {
                try VNImageRequestHandler(cgImage: imagem, options: [:]).perform([pedido])
                for o in pedido.results ?? [] {
                    let b = o.boundingBox          // Vision: origem embaixo à esquerda
                    rostos.append(["x": Double(b.minX), "y": Double(1 - b.maxY), "w": Double(b.width), "h": Double(b.height),
                                   "conf": Double(o.confidence)])
                }
            } catch { falhas += 1 }
        } else { falhas += 1 }
        quadros.append(["t": (t * 1000).rounded() / 1000, "rostos": rostos])
    }
}
if falhas == quadros.count { sair(1, "rostos: nenhum quadro pôde ser lido ou analisado (\(falhas) falha(s))") }

let doc: [String: Any] = ["versao": 1, "detector": "Vision VNDetectFaceRectanglesRequest", "largura": Double(largura),
                          "altura": Double(altura), "duracao": duracao, "fps": fps, "inicio": inicio, "fim": fim,
                          "falhas": falhas, "quadros": quadros]
guard let dados = try? JSONSerialization.data(withJSONObject: doc, options: [.sortedKeys]) else { sair(1, "rostos: não consegui montar o JSON") }
do { try dados.write(to: saida) } catch { sair(1, "rostos: não consegui gravar \(saida.path): \(error.localizedDescription)") }
print("rostos: \(quadros.count) quadro(s) de \(inicio) a \(fim) s, \(quadros.filter { !($0["rostos"] as! [[String: Double]]).isEmpty }.count) com rosto")
