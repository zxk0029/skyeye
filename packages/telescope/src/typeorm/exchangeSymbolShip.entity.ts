import { Entity, PrimaryColumn, OneToOne, JoinTable } from 'typeorm';
import { Exchange } from './exchange.entity';
import { Symbol } from './symbol.entity';

@Entity()
export class ExchangeSymbolShip {
  @PrimaryColumn({ type: 'bigint', name: 'id' })
  id: number;

  @OneToOne(() => Symbol)
  @JoinTable()
  symbol: symbol;

  @OneToOne(() => Exchange)
  @JoinTable()
  exchange: Exchange;
}
