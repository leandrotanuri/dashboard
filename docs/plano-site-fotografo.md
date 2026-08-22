# Plano — Site próprio para fotógrafo de eventos esportivos

> Objetivo: dar autonomia a um fotógrafo (amigo do Leandro) que hoje depende da
> conta/marca de terceiro. Ele terá a **própria loja**, com o **próprio domínio,
> marca e Pix**, sem depender do chefe que boicota o trabalho dele.

## Contexto / referência analisada

Site de referência: `eusoquerofotografar.com.br` (apenas como referência de
**conceito**, NÃO cópia). Não é fotografia de casamento/retrato — é **fotografia
esportiva de eventos**: corridas de rua, maratonas, provas de ciclismo (interior
de SP, ex.: Corrida Tartaruga, Piratas do Asfalto, Corrida do SESI).

### Ponto-chave (por que ele é refém hoje)
O site de referência roda em cima da plataforma terceira **`fotop.com.br`** (SaaS
white-label pra fotógrafo de evento). A conta fotop é provavelmente **do chefe** —
por isso as fotos, os clientes e o dinheiro passam todos pela marca de outra
pessoa. A solução é ele ter a **loja própria**.

## Modelo de negócio (o fluxo a recriar)

1. Fotógrafo cobre o evento (milhares de fotos dos participantes).
2. Fotos vão para uma **galeria online organizada por evento**.
3. Participante **acha as próprias fotos**.
4. **Compra e baixa** (foto avulsa ou pacote).
5. Paga (Pix/cartão) e recebe o download.

## Decisões tomadas (rodada 1)

| Tema | Decisão |
|------|---------|
| **Busca de fotos** | **Reconhecimento facial** (participante manda selfie → sistema acha as fotos). Parte mais pesada; fase 2 depois do MVP. |
| **Pagamento** | **Mercado Pago (Pix + cartão)** — Pix cai na hora, API boa pra liberar download após pagar. |
| **Entrega desta rodada** | **Protótipo navegável** — site de demonstração com fotos de exemplo, pra validar a ideia antes de investir mais. |

## Próximos passos (quando retomarmos)

1. Construir o **protótipo navegável** (foco desta rodada):
   - Home/landing (marca do fotógrafo, prova social, chamada pra achar fotos).
   - Lista de eventos → álbum do evento → grade de fotos.
   - Fluxo de "achar minhas fotos" (mock de reconhecimento facial via selfie).
   - Carrinho + checkout (mock do Mercado Pago Pix/cartão).
   - Página de download pós-pagamento (mock).
   - Fotos de exemplo (placeholders), marca genérica ("Nome do Fotógrafo").
2. Validar com o amigo.
3. Depois do OK: definir domínio, hospedagem e conta Mercado Pago reais.
4. Fase 2: integração real de pagamento + reconhecimento facial.

## Pendências para o amigo decidir (fase MVP real)
- Nome/marca e domínio.
- Conta Mercado Pago (CPF/CNPJ dele).
- Hospedagem.
- Política de preços (foto avulsa x pacote x "todas do evento").
- Provedor de reconhecimento facial (build vs. serviço pronto) e custo.

---
_Status: pausado a pedido do Leandro. Decisões da rodada 1 salvas. Retomar pelo
"Próximos passos" item 1 (protótipo navegável)._
