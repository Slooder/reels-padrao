// Recorta o objeto principal de uma imagem (Vision · VNGenerateForegroundInstanceMaskRequest) e salva PNG com alfa.
import Foundation
import Vision
import CoreImage
import AppKit
let a = CommandLine.arguments
let inURL = URL(fileURLWithPath: a[1]), outURL = URL(fileURLWithPath: a[2])
guard let ci = CIImage(contentsOf: inURL) else { print("erro ao abrir"); exit(1) }
let handler = VNImageRequestHandler(ciImage: ci, options: [:])
let req = VNGenerateForegroundInstanceMaskRequest()
try handler.perform([req])
guard let obs = req.results?.first else { print("nenhum objeto"); exit(2) }
print("instancias:", obs.allInstances.count)
let buf = try obs.generateMaskedImage(ofInstances: obs.allInstances, from: handler, croppedToInstancesExtent: false)
let out = CIImage(cvPixelBuffer: buf)
let ctx = CIContext()
try ctx.writePNGRepresentation(of: out, to: outURL, format: .RGBA8, colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!)
print("ok", out.extent)
