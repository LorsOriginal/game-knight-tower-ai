import random

import pygame

from core.assets import AssetManager
from core.settings import HEIGHT, TILE_SIZE, WIDTH
from entities.player import Player
from systems.level import criar_mapa
from ui.hud import Hud


import pygame
import random

class GameScene:
    def __init__(self, assets: AssetManager):
        """
        Inicializa a cena principal do jogo, carregando recursos (imagens/sons)
        e preparando o estado do nível.
        """
        self.assets = assets
        self.tile_size = TILE_SIZE
        self.stage = 1  # Fase/Estágio atual do jogador

        # Carrega as folhas de sprites (spritesheets) e define as imagens base
        self.dungeon = self.assets.load_image("dungeon", "Dungeon_Tileset.png")
        self.key_sprite = self.assets.load_image("key", "keys.png", scale=(TILE_SIZE, TILE_SIZE))

        # Configura os efeitos sonoros e seus respectivos volumes
        self.sound_key = self.assets.load_sound("key", "mixkit-fairy-arcade-sparkle-866.wav", volume=0.5)
        self.sound_door = self.assets.load_sound("door", "mixkit-prison-metal-door-close-201.wav", volume=0.4)

        # Inicializa a interface de usuário (Heads-Up Display) passando o ícone da chave
        self.hud = Hud(self.key_sprite)
        
        # Cria o dicionário de tiles e desenha as camadas que não mudam durante a fase
        self._build_tile_set()
        self._build_static_layers()
        
        # Define o estado inicial da fase atual (posição de itens, inimigos, etc.)
        self.reset_level_state()

    def _get_tile(self, col: int, row: int, tw: int = 16, th: int = 16) -> pygame.Surface:
        """
        Corta um pedaço (tile) da imagem do tileset com base na coluna e linha informadas,
        redimensionando-o para o tamanho padrão do jogo (TILE_SIZE).
        """
        surface = pygame.Surface((tw, th), pygame.SRCALPHA)
        # Copia apenas o retângulo correspondente ao tile da imagem original da dungeon
        surface.blit(self.dungeon, (0, 0), (col * tw, row * th, tw, th))
        # Escala o tile cortado para o tamanho final de renderização
        return pygame.transform.scale(surface, (self.tile_size, self.tile_size))

    def _build_tile_set(self):
        """
        Mapeia e recorta todos os blocos necessários do tileset (chão, paredes, portas e decorações).
        """
        # Cria uma lista com variações de blocos de chão para que o piso não fique repetitivo
        self.floor_tiles = [self._get_tile(c, r) for r in (1, 2, 3) for c in (1, 2, 3)]
        
        # Dicionário mapeando os nomes das conexões de parede para seus respectivos recortes
        self.wall_tiles = {
            "canto_sup_esq": self._get_tile(0, 0),
            "canto_sup_dir": self._get_tile(5, 5),
            "canto_inf_esq": self._get_tile(0, 4),
            "canto_inf_dir": self._get_tile(5, 4),
            "topo":          self._get_tile(1, 0),
            "base":          self._get_tile(1, 4),
            "lat_esq":       self._get_tile(0, 1),
            "lat_dir":       self._get_tile(5, 1),
            "interior":      self._get_tile(4, 9),
            "isolado":       self._get_tile(3, 0),
            "ponta_cima":    self._get_tile(0, 3),
            "ponta_baixo":   self._get_tile(5, 1),
            "ponta_esq":     self._get_tile(4, 0),
            "ponta_dir":     self._get_tile(2, 0),
        }
        # Define os estados visualmente distintos para a porta de saída
        self.door_closed = self._get_tile(7, 5)
        self.door_open = self._get_tile(7, 6)
        
        # Mapeia decorações estáticas e suas coordenadas pré-definidas na grade do mapa
        self.decorations = {
            self._get_tile(4, 3): [(1, 1), (18, 1), (1, 12), (18, 12)], # Ex: Tochas/estátuas nos cantos
            self._get_tile(9, 5): [(2, 1), (17, 1), (2, 12), (17, 12)],
            self._get_tile(7, 7): [(5, 4), (10, 7), (14, 3)],           # Ex: Detalhes de rachaduras no chão
            self._get_tile(8, 6): [(7, 9), (13, 10)],
        }

    def _build_static_layers(self):
        """
        Gera as superfícies estáticas de fundo (piso e decorações).
        Isso otimiza o desempenho, pois evita redesenhar tile por tile a cada frame.
        """
        random.seed(99) # Garante que o chão seja gerado aleatoriamente da mesma forma sempre
        
        # 1. Cria a camada do chão (piso completo)
        self.floor_surface = pygame.Surface((WIDTH, HEIGHT))
        for ry in range(HEIGHT // self.tile_size + 1):
            for rx in range(WIDTH // self.tile_size + 1):
                # Escolhe um bloco de chão aleatório da lista para criar variedade visual
                tile_aleatorio = random.choice(self.floor_tiles)
                self.floor_surface.blit(tile_aleatorio, (rx * self.tile_size, ry * self.tile_size))

        # 2. Cria a camada de decorações (com canal Alpha para transparência)
        self.deco_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for sprite, positions in self.decorations.items():
            for gx, gy in positions:
                self.deco_surface.blit(sprite, (gx * self.tile_size, gy * self.tile_size))

    def reset_level_state(self):
        """
        Reinicia ou reconstrói o estado lógico da fase atual.
        Chamado ao iniciar o jogo, ao morrer ou ao avançar de estágio.
        """
        self.collected_keys = 0
        self.door_is_open = False
        
        # 'criar_mapa' devolve os dados estruturados do layout do nível atual
        self.walls, player_position, self.keys, self.door, self.enemies = criar_mapa()
        
        # Instancia o jogador na coordenada inicial gerada pelo mapa
        self.player = Player(player_position[0], player_position[1])
        self.total_keys = len(self.keys)
        
        # Mapeia as posições das paredes em coordenadas de grade (X, Y) para facilitar a busca
        wall_positions = {(wall.x // self.tile_size, wall.y // self.tile_size) for wall in self.walls}
        
        # Processa o "Autotiling": associa cada objeto de parede ao sprite correto baseado em seus vizinhos
        self.wall_sprites = [
            (wall, self._choose_wall_tile(wall_positions, wall.x // self.tile_size, wall.y // self.tile_size)) 
            for wall in self.walls
        ]

    def _choose_wall_tile(self, wall_positions: set[tuple[int, int]], gx: int, gy: int) -> pygame.Surface:
        """
        Algoritmo de Autotiling. Analisa quais direções (Cima, Baixo, Esquerda, Direita) possuem 
        outras paredes vizinhas para escolher a textura de conexão ideal.
        """
        c = (gx, gy - 1) in wall_positions  # Vizinho de Cima existe?
        b = (gx, gy + 1) in wall_positions  # Vizinho de Baixo existe?
        e = (gx - 1, gy) in wall_positions  # Vizinho da Esquerda existe?
        d = (gx + 1, gy) in wall_positions  # Vizinho da Direita existe?
        t = self.wall_tiles
        
        # Casos Isolados ou Pontas Soltas
        if not c and not b and not e and not d: return t["isolado"]
        if c and not b and not e and not d: return t["ponta_cima"]
        if not c and b and not e and not d: return t["ponta_baixo"]
        if not c and not b and e and not d: return t["ponta_esq"]
        if not c and not b and not e and d: return t["ponta_dir"]
        
        # Cantos Externos
        if not c and not e and b and d: return t["canto_sup_esq"]
        if not c and not d and b and e: return t["canto_sup_dir"]
        if not b and not e and c and d: return t["canto_inf_esq"]
        if not b and not d and c and e: return t["canto_inf_dir"]
        
        # Paredes Retas e Corredores Duplos
        if not c and not b and e and d: return t["topo"]
        if c and b and not e and not d: return t["lat_esq"]
        
        # Interseções em T e Junções de Paredes
        if c and b and e and not d: return t["lat_dir"]
        if c and b and d and not e: return t["lat_esq"]
        if c and e and d and not b: return t["base"]
        if b and e and d and not c: return t["topo"]
        
        # Casos de segurança secundários (Fallbacks de conexões simples)
        if not c and b: return t["topo"]
        if c and not b: return t["base"]
        if not e and d: return t["lat_esq"]
        if e and not d: return t["lat_dir"]
        
        # Completamente cercado por outras paredes
        return t["interior"]

    def update(self):
        """
        Executa a lógica de física, comandos e checagem de colisões a cada frame.
        """
        # Captura as teclas pressionadas e move o jogador tratando as colisões com as paredes
        keys = pygame.key.get_pressed()
        self.player.mover(keys, self.walls)

        # Atualiza a inteligência artificial de movimento de cada inimigo em direção ao jogador
        for enemy in self.enemies:
            enemy.mover(self.player, self.walls)

        # Lógica de Coleta de Chaves (Varre uma cópia da lista `[:]` para evitar bugs de remoção)
        for key in self.keys[:]:
            if self.player.rect.colliderect(key):
                self.keys.remove(key)
                self.collected_keys += 1
                self.sound_key.play()
                
                # Se todas as chaves foram pegas, abre a porta e toca o efeito sonoro de abertura
                if len(self.keys) == 0 and not self.door_is_open:
                    self.door_is_open = True
                    self.sound_door.play()

        # Condição de Vitória do Nível: Porta aberta e jogador encostou nela
        if self.door_is_open and self.player.rect.colliderect(self.door):
            self.stage += 1
            self.reset_level_state() # Carrega a próxima fase

        # Condição de Derrota: Se qualquer inimigo encostar no jogador, reinicia o nível atual
        for enemy in self.enemies:
            if self.player.rect.colliderect(enemy.rect):
                self.reset_level_state()

    def draw(self, screen: pygame.Surface):
        """
        Renderiza todos os elementos visuais na tela na ordem correta das camadas (Z-Index).
        """
        # 1. Camadas Inferiores (Fundo estático)
        screen.blit(self.floor_surface, (0, 0))
        screen.blit(self.deco_surface, (0, 0))

        # 2. Camada das Paredes
        for wall, sprite in self.wall_sprites:
            screen.blit(sprite, (wall.x, wall.y))

        # 3. Camada de Itens e Objetos do cenário (Portas e Chaves)
        door_sprite = self.door_open if self.door_is_open else self.door_closed
        screen.blit(door_sprite, (self.door.x, self.door.y))

        for key in self.keys:
            # Renderiza a chave centralizando levemente com um ajuste de offset (-10)
            screen.blit(self.key_sprite, (key.x - 10, key.y - 10))

        # 4. Camada das Entidades (Personagens e Monstros dinâmicos)
        self.player.desenhar(screen)
        for enemy in self.enemies:
            enemy.desenhar(screen)

        # 5. Camada Superior/Interface (HUD - Informações de texto fixas na tela)
        self.hud.draw(screen, self.collected_keys, self.total_keys, self.stage)
        self.player.desenhar(screen)
        for enemy in self.enemies:
            enemy.desenhar(screen)

        self.hud.draw(screen, self.collected_keys, self.total_keys, self.stage)
