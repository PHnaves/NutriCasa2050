from __future__ import annotations

from dataclasses import dataclass, field

NOMES_REFEICOES_PADRAO: dict[int, tuple[str, ...]] = {
    1: ("almoco",),
    2: ("almoco", "jantar"),
    3: ("cafe_da_manha", "almoco", "jantar"),
}


@dataclass(frozen=True)
class Ingrediente:
    id: str
    nome: str
    unidade: str
    categoria: str
    validade_dias: int
    preco_embalagem: float
    tamanho_embalagem: float

    @property
    def preco_unitario(self) -> float:
        return self.preco_embalagem / self.tamanho_embalagem


@dataclass(frozen=True)
class Receita:
    id: str
    nome: str
    tempo_min: int
    tags: frozenset[str]
    preferencia: float


@dataclass(frozen=True)
class Faixa:
    minimo: float
    maximo: float
    alvo: float


@dataclass(frozen=True)
class Membro:
    id: str
    nome: str
    fator_porcao: float
    tags_bloqueadas: frozenset[str]
    faixas: dict[str, Faixa]

    def pode_comer(self, receita: Receita) -> bool:
        return not (self.tags_bloqueadas & receita.tags)


@dataclass(frozen=True)
class Lote:
    id: str
    ingrediente_id: str
    quantidade: float
    dia_vencimento: int
    # None = lote de estoque inicial (nao recebe chegada nenhuma). Quando
    # preenchido, marca um "lote de compra" (S3-01/R10): a chegada so e
    # creditada a ESTE lote no dia exato da compra, nunca em outro —
    # evita a mesma compra ser contada em mais de um lote do ingrediente
    # quando existe mais de um (ver restricoes.chegada_do_lote).
    dia_compra: int | None = None


@dataclass(frozen=True)
class Catalogo:
    ingredientes: dict[str, Ingrediente]
    receitas: dict[str, Receita]
    matriz_a: dict[tuple[str, str], float]
    nutrientes: dict[tuple[str, str], float]
    lotes: dict[str, Lote]
    membros: dict[str, Membro]
    # (dia, refeicao) marcados por simulacao.cenarios.pular_refeicoes (S4-01).
    # So os baselines heuristicos (S4-02/03) leem isto — o solver (R1) exige
    # uma porcao completa em toda refeicao do horizonte, e nao tem como
    # pular uma so para um cenario especifico sem reescrever a restricao;
    # e uma simplificacao assumida e documentada, nao um bug.
    refeicoes_puladas: frozenset[tuple[int, str]] = frozenset()
    # ids de ingrediente marcados por simulacao.cenarios.esquecer_itens
    # (S4-01). O solver ja evita compra-los sozinho (o preco fica
    # proibitivo, R12/objetivo cuidam disso); os baselines (S4-02/03) NAO
    # olham preco na hora de decidir a compra habitual, entao precisam
    # deste sinal explicito — senao comprariam a quantidade normal mesmo
    # a um preco 1000x maior, e um descarte depois viraria um valor em
    # reais sem nenhum sentido.
    itens_esquecidos: frozenset[str] = frozenset()

    def total_receitas(self) -> int:
        return len(self.receitas)

    def total_ingredientes(self) -> int:
        return len(self.ingredientes)

    def quantidade(self, receita_id: str, ingrediente_id: str) -> float:
        return self.matriz_a.get((receita_id, ingrediente_id), 0.0)

    def nutriente(self, receita_id: str, nome: str) -> float:
        return self.nutrientes.get((receita_id, nome), 0.0)

    def ingredientes_da_receita(self, receita_id: str) -> list[str]:
        return [i for (r, i) in self.matriz_a if r == receita_id]

    def receitas_com_ingrediente(self, ingrediente_id: str) -> list[str]:
        return [r for (r, i) in self.matriz_a if i == ingrediente_id]

    def lotes_do_ingrediente(self, ingrediente_id: str) -> list[Lote]:
        return [lote for lote in self.lotes.values() if lote.ingrediente_id == ingrediente_id]

    def receitas_permitidas(self, membro: Membro) -> list[str]:
        return [r.id for r in self.receitas.values() if membro.pode_comer(r)]

    def ingredientes_orfaos(self) -> list[str]:
        return [
            ingrediente_id
            for ingrediente_id in self.ingredientes
            if len(self.receitas_com_ingrediente(ingrediente_id)) < 2
        ]


@dataclass(frozen=True)
class Pesos:
    """Pesos/fatores de conversao da funcao objetivo (docs/formulacao.md, Secao 4).

    custo, desperdicio, preparo, desvio e preferencia sao os cinco pesos dos
    termos do objetivo (o sexto, sobra de embalagem, usa o mesmo peso de
    desperdicio). folga, custo_por_minuto e valor_por_ponto_preferencia sao os
    fatores que convertem unidades nao-monetarias (minutos, gramas, nota de
    preferencia) para reais antes de somar.
    """

    custo: float = 1.0
    desperdicio: float = 1.0
    preparo: float = 1.0
    desvio: float = 1.0
    # Peso bem mais alto que os outros de proposito (card S3-06): a folga
    # existe para o modelo nunca recusar uma faixa nutricional impossivel,
    # NAO para ser usada de graca sempre que for mais barato que cozinhar
    # direito.
    folga: float = 1000.0
    preferencia: float = 1.0
    custo_por_minuto: float = 0.10
    valor_por_ponto_preferencia: float = 1.0


@dataclass(frozen=True)
class Parametros:
    horizonte: int
    refeicoes_por_dia: int = 3
    pratos_por_refeicao: int = 2
    orcamento: float = 0.0
    dias_compra: tuple[int, ...] = (1,)
    tempo_por_dia: float = float("inf")
    pesos: Pesos = field(default_factory=Pesos)

    @property
    def dias(self) -> tuple[int, ...]:
        return tuple(range(1, self.horizonte + 1))

    @property
    def refeicoes(self) -> tuple[str, ...]:
        nomes = NOMES_REFEICOES_PADRAO.get(self.refeicoes_por_dia)
        if nomes is not None:
            return nomes
        return tuple(f"refeicao_{i + 1}" for i in range(self.refeicoes_por_dia))


@dataclass
class Solucao:
    status: str
    tempo_segundos: float
    valor_objetivo: float | None
    cardapio: dict
    porcoes: dict
    compras: dict
    descartes: dict
    estoque: dict
    aderencia: dict
