import {
  Column,
  Entity,
  PrimaryColumn,
  OneToOne,
  ManyToMany,
  JoinTable,
} from 'typeorm';
import { Exchange } from './exchange.entity';
import { Asset } from './asset.entity';

@Entity()
export class Symbol {
  @PrimaryColumn({ type: 'bigint', name: 'id' })
  id: number;

  @Column({ type: 'varchar', length: 255 })
  name: string;

  @OneToOne(() => Asset)
  @JoinTable()
  base_asset: Asset;

  @OneToOne(() => Asset)
  @JoinTable()
  quote_asset: Asset;

  @Column({ type: 'int' })
  uint: number;

  @ManyToMany(() => Exchange)
  @JoinTable()
  exchanges: Exchange[];

  @Column({ type: 'varchar', length: 255 })
  status: string;

  @Column({ type: 'varchar', length: 255 })
  category: string;
}
